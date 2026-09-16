from django.contrib.auth import authenticate, password_validation
from rest_framework import serializers

from .bootstrap import uses_default_password
from .models import Department, User


class DepartmentBriefSerializer(serializers.ModelSerializer):
    class Meta:
        model = Department
        fields = ['id', 'code', 'name']


class UserBriefSerializer(serializers.ModelSerializer):
    """로그인 응답과 /me/에서 사용하는 사용자 표현."""

    department = DepartmentBriefSerializer(read_only=True)
    password_is_default = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            'id',
            'employee_no',
            'name',
            'role',
            'position',
            'department',
            'password_is_default',
        ]
        read_only_fields = fields

    def get_password_is_default(self, obj):
        return uses_default_password(obj)


class LoginSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=50)
    employee_no = serializers.CharField(max_length=20)
    password = serializers.CharField(write_only=True, style={'input_type': 'password'})

    def validate(self, attrs):
        user = authenticate(
            request=self.context.get('request'),
            employee_no=attrs['employee_no'].strip(),
            name=attrs['name'].strip(),
            password=attrs['password'],
        )
        if user is None:
            # 실패 사유를 구분하지 않는다 (specs/03-auth.md §1)
            raise serializers.ValidationError('INVALID_CREDENTIALS')
        attrs['user'] = user
        return attrs


class ChangePasswordSerializer(serializers.Serializer):
    current_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True)

    def validate_current_password(self, value):
        user = self.context['request'].user
        if not user.check_password(value):
            raise serializers.ValidationError('현재 비밀번호가 올바르지 않습니다.')
        return value

    def validate_new_password(self, value):
        user = self.context['request'].user
        password_validation.validate_password(value, user)
        return value

    def validate(self, attrs):
        if attrs['current_password'] == attrs['new_password']:
            raise serializers.ValidationError(
                {'new_password': '현재 비밀번호와 다른 비밀번호를 사용하세요.'}
            )
        return attrs

    def save(self, **kwargs):
        user = self.context['request'].user
        user.set_password(self.validated_data['new_password'])
        user.save(update_fields=['password'])
        return user
