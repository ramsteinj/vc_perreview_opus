"""직원용 평가 응답 시리얼라이저 (specs/07-api.md §3)."""

from rest_framework import serializers

from .models import EvaluationResponse, EvaluatorAssignment


class AnswerInputSerializer(serializers.Serializer):
    item = serializers.IntegerField()
    score = serializers.IntegerField(required=False, allow_null=True, min_value=1)
    comment = serializers.CharField(required=False, allow_blank=True, default='')


class DraftSaveSerializer(serializers.Serializer):
    """임시 저장. 부분 저장을 허용하므로 모든 필드가 선택이다."""

    answers = AnswerInputSerializer(many=True, required=False)
    overall_comment = serializers.CharField(required=False, allow_blank=True)


class ResponseCreateSerializer(serializers.Serializer):
    assignment = serializers.PrimaryKeyRelatedField(queryset=EvaluatorAssignment.objects.all())


class MyItemSerializer(serializers.Serializer):
    """평가지 상세의 항목 + 내 답변."""

    id = serializers.IntegerField()
    code = serializers.CharField()
    title = serializers.CharField()
    description = serializers.CharField()
    weight = serializers.DecimalField(max_digits=5, decimal_places=2)
    max_score = serializers.IntegerField()
    order = serializers.IntegerField()
    answer = serializers.SerializerMethodField()

    def get_answer(self, obj):
        answer = self.context['answers'].get(obj.id)
        return {
            'score': answer.score if answer else None,
            'comment': answer.comment if answer else '',
        }


def serialize_target(assignment):
    if assignment.target_user_id:
        target = assignment.target_user
        return {
            'id': target.id,
            'name': target.name,
            'employee_no': target.employee_no,
            'department_name': target.department.name if target.department else None,
        }
    target = assignment.target_department
    return {'id': target.id, 'name': target.name, 'code': target.code}


def serialize_cycle(cycle):
    return {
        'id': cycle.id,
        'name': cycle.name,
        'status': cycle.status,
        'starts_on': cycle.starts_on,
        'ends_on': cycle.ends_on,
    }


class MyResponseDetailSerializer(serializers.ModelSerializer):
    """평가지 상세. 항목·답변·진행률을 함께 싣는다."""

    cycle = serializers.SerializerMethodField()
    target = serializers.SerializerMethodField()
    target_type = serializers.CharField(source='assignment.target_type', read_only=True)
    round_display = serializers.CharField(source='get_round_display', read_only=True)
    items = serializers.SerializerMethodField()
    progress = serializers.SerializerMethodField()
    answered_count = serializers.SerializerMethodField()
    total_items = serializers.SerializerMethodField()
    editable = serializers.SerializerMethodField()

    class Meta:
        model = EvaluationResponse
        fields = [
            'id',
            'round',
            'round_display',
            'status',
            'editable',
            'progress',
            'answered_count',
            'total_items',
            'overall_comment',
            'submitted_at',
            'updated_at',
            'cycle',
            'target',
            'target_type',
            'items',
        ]

    @property
    def _detail(self):
        return self.context['detail']

    def get_cycle(self, obj):
        return serialize_cycle(obj.assignment.cycle)

    def get_target(self, obj):
        return serialize_target(obj.assignment)

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

    def get_editable(self, obj):
        return self._detail['editable']


class MyResponseSummarySerializer(serializers.ModelSerializer):
    """저장·제출 응답에서 쓰는 경량 표현."""

    progress = serializers.IntegerField(read_only=True)
    answered_count = serializers.IntegerField(read_only=True)
    total_items = serializers.IntegerField(read_only=True)

    class Meta:
        model = EvaluationResponse
        fields = [
            'id',
            'round',
            'status',
            'progress',
            'answered_count',
            'total_items',
            'overall_comment',
            'submitted_at',
            'updated_at',
        ]
