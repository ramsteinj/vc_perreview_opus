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
