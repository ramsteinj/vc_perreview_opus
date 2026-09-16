from rest_framework import serializers

from apps.evaluations.models import EvaluationResponse
from apps.evaluations.serializers_my import MyItemSerializer, serialize_cycle, serialize_target


class ReopenSerializer(serializers.Serializer):
    reason = serializers.CharField(required=False, allow_blank=True, max_length=500)


class AdminResponseDetailSerializer(serializers.ModelSerializer):
    """관리자용 평가지 열람. 직원용과 달리 평가자 정보를 포함한다."""

    cycle = serializers.SerializerMethodField()
    target = serializers.SerializerMethodField()
    target_type = serializers.CharField(source='assignment.target_type', read_only=True)
    round_display = serializers.CharField(source='get_round_display', read_only=True)
    evaluator = serializers.SerializerMethodField()
    items = serializers.SerializerMethodField()
    progress = serializers.SerializerMethodField()
    answered_count = serializers.SerializerMethodField()
    total_items = serializers.SerializerMethodField()

    class Meta:
        model = EvaluationResponse
        fields = [
            'id',
            'round',
            'round_display',
            'status',
            'progress',
            'answered_count',
            'total_items',
            'overall_comment',
            'submitted_at',
            'updated_at',
            'cycle',
            'target',
            'target_type',
            'evaluator',
            'items',
        ]

    @property
    def _detail(self):
        return self.context['detail']

    def get_cycle(self, obj):
        return serialize_cycle(obj.assignment.cycle)

    def get_target(self, obj):
        return serialize_target(obj.assignment)

    def get_evaluator(self, obj):
        return {
            'id': obj.evaluator.id,
            'employee_no': obj.evaluator.employee_no,
            'name': obj.evaluator.name,
            'department_name': (
                obj.evaluator.department.name if obj.evaluator.department else None
            ),
        }

    def get_items(self, obj):
        return MyItemSerializer(
            self._detail['items'], many=True, context={'answers': self._detail['answers']}
        ).data

    def get_progress(self, obj):
        return self._detail['progress']['progress']

    def get_answered_count(self, obj):
        return self._detail['progress']['answered_count']

    def get_total_items(self, obj):
        return self._detail['progress']['total_items']


class ScoreResultSerializer(serializers.ModelSerializer):
    """최종 점수 목록 행."""

    user = serializers.SerializerMethodField()

    class Meta:
        from .models import ScoreResult

        model = ScoreResult
        fields = [
            'id',
            'user',
            'primary_score',
            'secondary_score',
            'individual_score',
            'department_score',
            'department_adjustment',
            'final_score',
            'calculated_at',
        ]

    def get_user(self, obj):
        return {
            'id': obj.user.id,
            'employee_no': obj.user.employee_no,
            'name': obj.user.name,
            'position': obj.user.position,
            'department_id': obj.department_id,
            'department_name': obj.department.name if obj.department else None,
        }


class _Score(serializers.DecimalField):
    """점수 표현용 공통 필드. API 전체에서 소수 둘째 자리 문자열로 통일한다."""

    def __init__(self, **kwargs):
        kwargs.setdefault('max_digits', 6)
        kwargs.setdefault('decimal_places', 2)
        kwargs.setdefault('allow_null', True)
        kwargs.setdefault('required', False)
        super().__init__(**kwargs)


class DepartmentScoreRowSerializer(serializers.Serializer):
    """부서 성과 점수 행 (FR-A-08)."""

    department_id = serializers.IntegerField()
    department_code = serializers.CharField()
    department_name = serializers.CharField()
    primary_score = _Score()
    secondary_score = _Score()
    department_score = _Score()
    inherited_score = _Score()
    department_adjustment = _Score()
    member_count = serializers.IntegerField()
    evaluated = serializers.BooleanField()


class AdjustParametersSerializer(serializers.Serializer):
    baseline = _Score()
    factor = _Score()
    limit = _Score()
