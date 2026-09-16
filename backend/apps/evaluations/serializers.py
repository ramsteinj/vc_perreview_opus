from decimal import Decimal

from rest_framework import serializers

from apps.accounts.models import Department, User

from .models import CycleStatus, EvaluationCycle, EvaluationItem, EvaluatorAssignment, TargetType


class EvaluatorBriefSerializer(serializers.ModelSerializer):
    department_name = serializers.CharField(source='department.name', read_only=True)

    class Meta:
        model = User
        fields = ['id', 'employee_no', 'name', 'department_name']


# ── 회차 ─────────────────────────────────────────────────────────
class EvaluationCycleSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    item_count = serializers.IntegerField(read_only=True)
    assignment_count = serializers.IntegerField(read_only=True)
    is_editable = serializers.BooleanField(read_only=True)

    class Meta:
        model = EvaluationCycle
        fields = [
            'id',
            'name',
            'year',
            'starts_on',
            'ends_on',
            'status',
            'status_display',
            'primary_weight',
            'secondary_weight',
            'dept_baseline_score',
            'dept_adjust_factor',
            'dept_adjust_limit',
            'item_count',
            'assignment_count',
            'is_editable',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['status', 'created_at', 'updated_at']

    def validate(self, attrs):
        instance = self.instance
        starts_on = attrs.get('starts_on', getattr(instance, 'starts_on', None))
        ends_on = attrs.get('ends_on', getattr(instance, 'ends_on', None))
        primary = attrs.get('primary_weight', getattr(instance, 'primary_weight', Decimal('70')))
        secondary = attrs.get(
            'secondary_weight', getattr(instance, 'secondary_weight', Decimal('30'))
        )

        errors = {}
        if starts_on and ends_on and starts_on > ends_on:
            errors['ends_on'] = '마감일은 시작일 이후여야 합니다.'
        if Decimal(primary) + Decimal(secondary) != Decimal('100'):
            errors['primary_weight'] = '1차와 2차 반영비율의 합은 100이어야 합니다.'
        if errors:
            raise serializers.ValidationError(errors)

        if instance is not None and instance.status == CycleStatus.CLOSED:
            raise serializers.ValidationError(
                {'code': 'CYCLE_NOT_EDITABLE', 'detail': '마감된 회차는 수정할 수 없습니다.'}
            )

        return attrs


# ── 평가 항목 ────────────────────────────────────────────────────
class EvaluationItemSerializer(serializers.ModelSerializer):
    in_use = serializers.SerializerMethodField()
    target_type_display = serializers.CharField(source='get_target_type_display', read_only=True)

    class Meta:
        model = EvaluationItem
        fields = [
            'id',
            'cycle',
            'target_type',
            'target_type_display',
            'code',
            'title',
            'description',
            'weight',
            'max_score',
            'order',
            'is_active',
            'in_use',
        ]

    def get_in_use(self, obj):
        return obj.in_use

    def validate_weight(self, value):
        if value <= 0:
            raise serializers.ValidationError('가중치는 0보다 커야 합니다.')
        if value > 100:
            raise serializers.ValidationError('가중치는 100을 넘을 수 없습니다.')
        return value

    def validate_code(self, value):
        return value.strip().upper()

    def validate(self, attrs):
        instance = self.instance
        cycle = attrs.get('cycle', getattr(instance, 'cycle', None))
        target_type = attrs.get('target_type', getattr(instance, 'target_type', None))
        code = attrs.get('code', getattr(instance, 'code', None))

        if cycle is not None and cycle.status == CycleStatus.CLOSED:
            raise serializers.ValidationError(
                {'code': 'CYCLE_NOT_EDITABLE', 'detail': '마감된 회차는 수정할 수 없습니다.'}
            )

        duplicate = EvaluationItem.objects.filter(cycle=cycle, target_type=target_type, code=code)
        if instance is not None:
            duplicate = duplicate.exclude(pk=instance.pk)
        if duplicate.exists():
            raise serializers.ValidationError(
                {'code': '같은 회차·대상 유형에 이미 있는 코드입니다.'}
            )

        return attrs


class ItemReorderSerializer(serializers.Serializer):
    cycle = serializers.PrimaryKeyRelatedField(queryset=EvaluationCycle.objects.all())
    item_ids = serializers.ListField(child=serializers.IntegerField(), allow_empty=False)


class CloneItemsSerializer(serializers.Serializer):
    source_cycle = serializers.PrimaryKeyRelatedField(queryset=EvaluationCycle.objects.all())
    target_type = serializers.ChoiceField(choices=TargetType.choices, required=False)
    replace = serializers.BooleanField(default=False)


# ── 평가자 배정 ──────────────────────────────────────────────────
class EvaluatorAssignmentSerializer(serializers.ModelSerializer):
    primary_evaluator_detail = EvaluatorBriefSerializer(source='primary_evaluator', read_only=True)
    secondary_evaluator_detail = EvaluatorBriefSerializer(
        source='secondary_evaluator', read_only=True
    )
    target_name = serializers.CharField(read_only=True)

    class Meta:
        model = EvaluatorAssignment
        fields = [
            'id',
            'cycle',
            'target_type',
            'target_user',
            'target_department',
            'target_name',
            'primary_evaluator',
            'primary_evaluator_detail',
            'secondary_evaluator',
            'secondary_evaluator_detail',
            'created_at',
            'updated_at',
        ]
        # 모델의 조건부 UniqueConstraint에서 DRF가 자동 생성하는 UniqueTogetherValidator는
        # target_user/target_department를 모두 필수로 만들어 버린다.
        # 대상 유형에 따라 둘 중 하나만 채우는 구조이므로 끄고 validate()에서 직접 검사한다.
        validators = []

    def validate(self, attrs):
        instance = self.instance

        def current(field):
            return attrs.get(field, getattr(instance, field, None))

        cycle = current('cycle')
        target_type = current('target_type')
        target_user = current('target_user')
        target_department = current('target_department')
        primary = current('primary_evaluator')
        secondary = attrs.get('secondary_evaluator', getattr(instance, 'secondary_evaluator', None))

        if cycle is not None and cycle.status == CycleStatus.CLOSED:
            raise serializers.ValidationError(
                {'code': 'CYCLE_NOT_EDITABLE', 'detail': '마감된 회차는 수정할 수 없습니다.'}
            )

        errors = {}

        if target_type == TargetType.EMPLOYEE:
            if target_user is None:
                errors['target_user'] = '개인 평가는 평가 대상 직원이 필요합니다.'
            if target_department is not None:
                errors['target_department'] = '개인 평가에는 부서를 지정할 수 없습니다.'
        elif target_type == TargetType.DEPARTMENT:
            if target_department is None:
                errors['target_department'] = '부서 평가는 평가 대상 부서가 필요합니다.'
            if target_user is not None:
                errors['target_user'] = '부서 평가에는 직원을 지정할 수 없습니다.'

        if primary is None:
            errors['primary_evaluator'] = '1차 평가자는 필수입니다.'

        if secondary is not None and primary is not None and secondary.pk == primary.pk:
            errors['secondary_evaluator'] = '1차와 2차 평가자는 서로 달라야 합니다.'

        if target_type == TargetType.EMPLOYEE and target_user is not None:
            if primary is not None and primary.pk == target_user.pk:
                errors['primary_evaluator'] = '본인을 본인의 평가자로 지정할 수 없습니다.'
            if secondary is not None and secondary.pk == target_user.pk:
                errors['secondary_evaluator'] = '본인을 본인의 평가자로 지정할 수 없습니다.'

        if errors:
            raise serializers.ValidationError(errors)

        # 중복 배정 검사 (DB UniqueConstraint의 사전 방어)
        duplicate = EvaluatorAssignment.objects.filter(cycle=cycle, target_type=target_type)
        if target_type == TargetType.EMPLOYEE:
            duplicate = duplicate.filter(target_user=target_user)
        else:
            duplicate = duplicate.filter(target_department=target_department)
        if instance is not None:
            duplicate = duplicate.exclude(pk=instance.pk)
        if duplicate.exists():
            raise serializers.ValidationError(
                {'code': 'ALREADY_ASSIGNED', 'detail': '이미 배정된 대상입니다.'}
            )

        return attrs


class BulkAssignSerializer(serializers.Serializer):
    cycle = serializers.PrimaryKeyRelatedField(queryset=EvaluationCycle.objects.all())
    target_type = serializers.ChoiceField(choices=TargetType.choices)
    primary_evaluator = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.filter(is_active=True)
    )
    secondary_evaluator = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.filter(is_active=True), required=False, allow_null=True
    )
    department = serializers.PrimaryKeyRelatedField(
        queryset=Department.objects.all(), required=False, allow_null=True
    )
    target_ids = serializers.ListField(
        child=serializers.IntegerField(), required=False, allow_empty=False
    )
    overwrite = serializers.BooleanField(default=False)

    def validate(self, attrs):
        primary = attrs['primary_evaluator']
        secondary = attrs.get('secondary_evaluator')
        if secondary is not None and secondary.pk == primary.pk:
            raise serializers.ValidationError(
                {'secondary_evaluator': '1차와 2차 평가자는 서로 달라야 합니다.'}
            )
        if not attrs.get('department') and not attrs.get('target_ids'):
            raise serializers.ValidationError(
                {'detail': '부서 또는 대상 목록 중 하나는 지정해야 합니다.'}
            )
        return attrs
