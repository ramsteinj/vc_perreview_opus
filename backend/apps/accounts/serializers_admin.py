"""관리자용 부서/사용자 시리얼라이저 (specs/05-admin-features.md FR-A-02, FR-A-03)."""

from django.contrib.auth import password_validation
from rest_framework import serializers
from rest_framework.validators import UniqueValidator

from apps.common.exceptions import LastAdminError, SelfRoleDowngradeError

from .models import Department, Role, User
from .services import is_last_active_admin


# ── 부서 ─────────────────────────────────────────────────────────
class DepartmentSerializer(serializers.ModelSerializer):
    parent_name = serializers.CharField(source='parent.name', read_only=True)
    member_count = serializers.IntegerField(read_only=True)
    child_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Department
        fields = [
            'id',
            'code',
            'name',
            'parent',
            'parent_name',
            'is_active',
            'member_count',
            'child_count',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['created_at', 'updated_at']

    def validate_parent(self, value):
        """자기 자신 또는 자손을 상위 부서로 지정할 수 없다."""
        if value is None:
            return value

        instance = self.instance
        if instance is None:
            return value

        if value.pk == instance.pk:
            raise serializers.ValidationError('자기 자신을 상위 부서로 지정할 수 없습니다.')

        # value에서 루트까지 거슬러 올라가며 instance를 만나면 순환이다
        seen = set()
        node = value
        while node is not None:
            if node.pk in seen:
                break
            seen.add(node.pk)
            if node.pk == instance.pk:
                raise serializers.ValidationError('하위 부서를 상위 부서로 지정할 수 없습니다.')
            node = node.parent

        return value


class DepartmentTreeSerializer(serializers.ModelSerializer):
    children = serializers.SerializerMethodField()
    member_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Department
        fields = ['id', 'code', 'name', 'is_active', 'member_count', 'children']

    def get_children(self, obj):
        children = self.context['children_map'].get(obj.pk, [])
        return DepartmentTreeSerializer(children, many=True, context=self.context).data


# ── 사용자 ───────────────────────────────────────────────────────
class AdminUserListSerializer(serializers.ModelSerializer):
    """목록용. 비밀번호 해시 연산이 필요한 필드를 포함하지 않는다."""

    department_name = serializers.CharField(source='department.name', read_only=True)
    department_code = serializers.CharField(source='department.code', read_only=True)
    role_display = serializers.CharField(source='get_role_display', read_only=True)

    class Meta:
        model = User
        fields = [
            'id',
            'employee_no',
            'name',
            'department',
            'department_name',
            'department_code',
            'position',
            'role',
            'role_display',
            'hired_on',
            'is_active',
            'last_login',
            'date_joined',
        ]


class AdminUserCreateSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=False, allow_blank=False)

    class Meta:
        model = User
        fields = [
            'id',
            'employee_no',
            'name',
            'department',
            'position',
            'role',
            'hired_on',
            'is_active',
            'password',
        ]
        extra_kwargs = {
            'employee_no': {
                'validators': [
                    UniqueValidator(
                        queryset=User.objects.all(), message='이미 사용 중인 사번입니다.'
                    )
                ]
            }
        }

    def validate_employee_no(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError('사번을 입력하세요.')
        if User.objects.filter(employee_no=value).exists():
            raise serializers.ValidationError('이미 사용 중인 사번입니다.')
        return value

    def validate_name(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError('성명을 입력하세요.')
        return value

    def validate_password(self, value):
        password_validation.validate_password(value)
        return value

    def create(self, validated_data):
        from .services import generate_temporary_password

        password = validated_data.pop('password', None)
        generated = False
        if not password:
            password = generate_temporary_password()
            generated = True

        user = User.objects.create_user(password=password, **validated_data)

        # 생성 응답에서 1회만 노출하기 위해 인스턴스에 실어 보낸다
        user._generated_password = password if generated else None
        return user


class AdminUserUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            'id',
            'employee_no',
            'name',
            'department',
            'position',
            'role',
            'hired_on',
            'is_active',
        ]
        extra_kwargs = {
            'employee_no': {
                'validators': [
                    UniqueValidator(
                        queryset=User.objects.all(), message='이미 사용 중인 사번입니다.'
                    )
                ]
            }
        }

    def validate_employee_no(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError('사번을 입력하세요.')
        if User.objects.filter(employee_no=value).exclude(pk=self.instance.pk).exists():
            raise serializers.ValidationError('이미 사용 중인 사번입니다.')
        return value

    def validate(self, attrs):
        request = self.context['request']
        instance = self.instance

        new_role = attrs.get('role', instance.role)
        new_active = attrs.get('is_active', instance.is_active)

        # 본인의 권한을 스스로 낮출 수 없다
        if (
            instance.pk == request.user.pk
            and instance.role == Role.ADMIN
            and new_role != Role.ADMIN
        ):
            raise SelfRoleDowngradeError()

        # 마지막 관리자를 권한 강등하거나 비활성화할 수 없다
        losing_admin = instance.role == Role.ADMIN and (new_role != Role.ADMIN or not new_active)
        if losing_admin and is_last_active_admin(instance):
            raise LastAdminError()

        return attrs


class ResetPasswordSerializer(serializers.Serializer):
    """비밀번호를 지정하거나, 생략하면 임시 비밀번호를 생성한다."""

    password = serializers.CharField(write_only=True, required=False, allow_blank=False)

    def validate_password(self, value):
        password_validation.validate_password(value, self.context.get('target_user'))
        return value
