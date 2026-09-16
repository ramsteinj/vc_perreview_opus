from django.core.exceptions import ValidationError
from django.db import models

from apps.accounts.models import Department, User
from apps.common.models import TimeStampedModel


class TargetType(models.TextChoices):
    EMPLOYEE = 'EMPLOYEE', '개인'
    DEPARTMENT = 'DEPARTMENT', '부서'


class EvaluationRound(models.TextChoices):
    PRIMARY = 'PRIMARY', '1차'
    SECONDARY = 'SECONDARY', '2차'


class CycleStatus(models.TextChoices):
    DRAFT = 'DRAFT', '준비중'
    OPEN = 'OPEN', '진행중'
    CLOSED = 'CLOSED', '마감'


class ResponseStatus(models.TextChoices):
    DRAFT = 'DRAFT', '임시저장'
    SUBMITTED = 'SUBMITTED', '제출완료'


class EvaluationCycle(TimeStampedModel):
    """평가 회차. 항목·가중치·평가자 배정·응답이 모두 회차에 종속된다."""

    name = models.CharField('회차명', max_length=100)
    year = models.PositiveSmallIntegerField('평가연도')
    starts_on = models.DateField('응답 시작일')
    ends_on = models.DateField('응답 마감일')
    status = models.CharField(
        '상태', max_length=10, choices=CycleStatus.choices, default=CycleStatus.DRAFT
    )

    # 1차/2차 평가 반영 비율 (specs/06-scoring.md §3)
    primary_weight = models.DecimalField('1차 반영비율', max_digits=5, decimal_places=2, default=70)
    secondary_weight = models.DecimalField(
        '2차 반영비율', max_digits=5, decimal_places=2, default=30
    )

    # 부서 성과 가감 파라미터 (specs/06-scoring.md §5)
    dept_baseline_score = models.DecimalField(
        '부서 가감 기준점', max_digits=5, decimal_places=2, default=70
    )
    dept_adjust_factor = models.DecimalField(
        '부서 가감 계수', max_digits=5, decimal_places=2, default=0.20
    )
    dept_adjust_limit = models.DecimalField(
        '부서 가감 한도', max_digits=5, decimal_places=2, default=10
    )

    class Meta:
        verbose_name = '평가 회차'
        verbose_name_plural = '평가 회차'
        ordering = ['-year', '-starts_on']
        constraints = [
            models.CheckConstraint(
                condition=models.Q(starts_on__lte=models.F('ends_on')),
                name='cycle_starts_before_ends',
            ),
        ]

    def __str__(self):
        return self.name

    def clean(self):
        errors = {}
        if self.starts_on and self.ends_on and self.starts_on > self.ends_on:
            errors['ends_on'] = '마감일은 시작일 이후여야 합니다.'
        if self.primary_weight is not None and self.secondary_weight is not None:
            if self.primary_weight + self.secondary_weight != 100:
                errors['primary_weight'] = '1차와 2차 반영비율의 합은 100이어야 합니다.'
        if errors:
            raise ValidationError(errors)

    @property
    def is_open(self):
        return self.status == CycleStatus.OPEN

    @property
    def is_editable(self):
        """항목·배정을 수정할 수 있는 상태인지. 마감된 회차는 읽기 전용이다."""
        return self.status != CycleStatus.CLOSED


class EvaluationItem(TimeStampedModel):
    """평가 문항. 대상 유형(개인/부서)과 가중치를 가진다."""

    cycle = models.ForeignKey(
        EvaluationCycle, on_delete=models.CASCADE, related_name='items', verbose_name='회차'
    )
    target_type = models.CharField('대상유형', max_length=12, choices=TargetType.choices)
    code = models.CharField('항목코드', max_length=30)
    title = models.CharField('문항', max_length=200)
    description = models.TextField('평가기준', blank=True)
    weight = models.DecimalField('가중치', max_digits=5, decimal_places=2)
    max_score = models.PositiveSmallIntegerField('척도상한', default=5)
    order = models.PositiveIntegerField('순서', default=0)
    is_active = models.BooleanField('활성여부', default=True)

    class Meta:
        verbose_name = '평가 항목'
        verbose_name_plural = '평가 항목'
        ordering = ['cycle', 'target_type', 'order', 'id']
        constraints = [
            models.UniqueConstraint(
                fields=['cycle', 'target_type', 'code'], name='uniq_item_cycle_type_code'
            ),
            models.CheckConstraint(condition=models.Q(weight__gt=0), name='item_weight_positive'),
            models.CheckConstraint(
                condition=models.Q(max_score__gte=1), name='item_max_score_positive'
            ),
        ]
        indexes = [models.Index(fields=['cycle', 'target_type', 'is_active'])]

    def __str__(self):
        return f'[{self.get_target_type_display()}] {self.title}'

    @property
    def in_use(self):
        """이 항목에 응답이 하나라도 존재하는지. 존재하면 가중치·척도를 바꿀 수 없다."""
        if not hasattr(self, 'answers'):
            # Phase 4에서 EvaluationAnswer가 추가되기 전까지는 항상 False
            return False
        return self.answers.exists()


class EvaluatorAssignment(TimeStampedModel):
    """평가 대상 1건에 대한 1차/2차 평가자 지정. 2차는 선택이다."""

    cycle = models.ForeignKey(
        EvaluationCycle, on_delete=models.CASCADE, related_name='assignments', verbose_name='회차'
    )
    target_type = models.CharField('대상유형', max_length=12, choices=TargetType.choices)
    target_user = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='as_target',
        verbose_name='평가대상(직원)',
    )
    target_department = models.ForeignKey(
        Department,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='as_target',
        verbose_name='평가대상(부서)',
    )
    primary_evaluator = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='primary_assignments',
        verbose_name='1차 평가자',
    )
    secondary_evaluator = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='secondary_assignments',
        verbose_name='2차 평가자',
    )

    class Meta:
        verbose_name = '평가자 배정'
        verbose_name_plural = '평가자 배정'
        ordering = ['cycle', 'target_type', 'id']
        constraints = [
            models.UniqueConstraint(
                fields=['cycle', 'target_type', 'target_user'],
                condition=models.Q(target_user__isnull=False),
                name='uniq_assignment_cycle_user',
            ),
            models.UniqueConstraint(
                fields=['cycle', 'target_type', 'target_department'],
                condition=models.Q(target_department__isnull=False),
                name='uniq_assignment_cycle_department',
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(
                        target_type=TargetType.EMPLOYEE,
                        target_user__isnull=False,
                        target_department__isnull=True,
                    )
                    | models.Q(
                        target_type=TargetType.DEPARTMENT,
                        target_user__isnull=True,
                        target_department__isnull=False,
                    )
                ),
                name='assignment_target_matches_type',
            ),
        ]
        indexes = [
            models.Index(fields=['cycle', 'target_type']),
            models.Index(fields=['primary_evaluator']),
            models.Index(fields=['secondary_evaluator']),
        ]

    def __str__(self):
        return f'{self.cycle.name} · {self.target_name}'

    @property
    def target_name(self):
        if self.target_type == TargetType.EMPLOYEE:
            return self.target_user.name if self.target_user else '-'
        return self.target_department.name if self.target_department else '-'

    def clean(self):
        errors = {}

        if self.target_type == TargetType.EMPLOYEE:
            if self.target_user_id is None:
                errors['target_user'] = '개인 평가는 평가 대상 직원이 필요합니다.'
            if self.target_department_id is not None:
                errors['target_department'] = '개인 평가에는 부서를 지정할 수 없습니다.'
        elif self.target_type == TargetType.DEPARTMENT:
            if self.target_department_id is None:
                errors['target_department'] = '부서 평가는 평가 대상 부서가 필요합니다.'
            if self.target_user_id is not None:
                errors['target_user'] = '부서 평가에는 직원을 지정할 수 없습니다.'

        if (
            self.secondary_evaluator_id is not None
            and self.secondary_evaluator_id == self.primary_evaluator_id
        ):
            errors['secondary_evaluator'] = '1차와 2차 평가자는 서로 달라야 합니다.'

        if self.target_type == TargetType.EMPLOYEE and self.target_user_id is not None:
            if self.primary_evaluator_id == self.target_user_id:
                errors['primary_evaluator'] = '본인을 본인의 평가자로 지정할 수 없습니다.'
            if self.secondary_evaluator_id == self.target_user_id:
                errors['secondary_evaluator'] = '본인을 본인의 평가자로 지정할 수 없습니다.'

        if errors:
            raise ValidationError(errors)


class EvaluationResponse(TimeStampedModel):
    """평가자 1명이 대상 1개에 대해 작성하는 평가지 한 장.

    중복 응답 방지의 단위다. UniqueConstraint(assignment, round)가 최종 방어선이며
    애플리케이션 검증은 그 앞단의 사용자 친화적 안내 역할만 한다.
    """

    assignment = models.ForeignKey(
        EvaluatorAssignment,
        on_delete=models.CASCADE,
        related_name='responses',
        verbose_name='배정',
    )
    evaluator = models.ForeignKey(
        User, on_delete=models.PROTECT, related_name='responses', verbose_name='평가자'
    )
    round = models.CharField('차수', max_length=10, choices=EvaluationRound.choices)
    status = models.CharField(
        '상태', max_length=10, choices=ResponseStatus.choices, default=ResponseStatus.DRAFT
    )
    submitted_at = models.DateTimeField('제출일시', null=True, blank=True)
    overall_comment = models.TextField('종합의견', blank=True)

    class Meta:
        verbose_name = '평가지'
        verbose_name_plural = '평가지'
        ordering = ['-updated_at']
        constraints = [
            models.UniqueConstraint(
                fields=['assignment', 'round'], name='uniq_response_assignment_round'
            ),
        ]
        indexes = [
            models.Index(fields=['evaluator', 'status']),
            models.Index(fields=['assignment', 'round']),
        ]

    def __str__(self):
        return f'{self.assignment.target_name} · {self.get_round_display()}'

    @property
    def cycle(self):
        return self.assignment.cycle

    @property
    def is_submitted(self):
        return self.status == ResponseStatus.SUBMITTED

    @property
    def expected_evaluator_id(self):
        """이 차수의 평가자로 지정된 사용자 ID."""
        if self.round == EvaluationRound.PRIMARY:
            return self.assignment.primary_evaluator_id
        return self.assignment.secondary_evaluator_id


class EvaluationAnswer(models.Model):
    """평가지 내 개별 항목에 대한 점수와 의견.

    임시 저장 중에는 score가 null일 수 있다. 제출 시점에는 모든 활성 항목의
    score가 채워져 있어야 한다.
    """

    response = models.ForeignKey(
        EvaluationResponse,
        on_delete=models.CASCADE,
        related_name='answers',
        verbose_name='평가지',
    )
    item = models.ForeignKey(
        EvaluationItem, on_delete=models.PROTECT, related_name='answers', verbose_name='항목'
    )
    score = models.PositiveSmallIntegerField('점수', null=True, blank=True)
    comment = models.TextField('의견', blank=True)
    updated_at = models.DateTimeField('수정일시', auto_now=True)

    class Meta:
        verbose_name = '평가 답변'
        verbose_name_plural = '평가 답변'
        ordering = ['item__order', 'item_id']
        constraints = [
            models.UniqueConstraint(fields=['response', 'item'], name='uniq_answer_response_item'),
            models.CheckConstraint(
                condition=models.Q(score__isnull=True) | models.Q(score__gte=1),
                name='answer_score_min',
            ),
        ]

    def __str__(self):
        return f'{self.item.code}={self.score}'

    def clean(self):
        errors = {}
        if self.score is not None and self.item_id:
            if self.score < 1 or self.score > self.item.max_score:
                errors['score'] = f'점수는 1 ~ {self.item.max_score} 사이여야 합니다.'
        if errors:
            raise ValidationError(errors)
