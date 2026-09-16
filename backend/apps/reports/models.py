"""산출된 점수 스냅샷 (specs/02-data-model.md §5.1)."""

from django.db import models

from apps.accounts.models import Department, User
from apps.evaluations.models import EvaluationCycle


class ScoreResult(models.Model):
    """회차별 피평가자 최종 점수.

    계산 결과를 캐싱하고 이력을 보존한다. 재산출 시 update_or_create로 갱신한다.
    department는 산출 시점의 소속 부서 스냅샷이다 (이후 부서 이동과 무관하게 보존).
    """

    cycle = models.ForeignKey(
        EvaluationCycle,
        on_delete=models.CASCADE,
        related_name='score_results',
        verbose_name='회차',
    )
    user = models.ForeignKey(
        User, on_delete=models.PROTECT, related_name='score_results', verbose_name='피평가자'
    )
    department = models.ForeignKey(
        Department,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='score_results',
        verbose_name='산출시점 부서',
    )

    primary_score = models.DecimalField(
        '1차 환산점수', max_digits=6, decimal_places=2, null=True, blank=True
    )
    secondary_score = models.DecimalField(
        '2차 환산점수', max_digits=6, decimal_places=2, null=True, blank=True
    )
    individual_score = models.DecimalField('개인 평가점수', max_digits=6, decimal_places=2)
    department_score = models.DecimalField(
        '부서 성과점수', max_digits=6, decimal_places=2, null=True, blank=True
    )
    department_adjustment = models.DecimalField(
        '부서 가감', max_digits=6, decimal_places=2, default=0
    )
    final_score = models.DecimalField('최종 점수', max_digits=6, decimal_places=2)

    calculated_at = models.DateTimeField('산출일시', auto_now=True)

    class Meta:
        verbose_name = '점수 산출 결과'
        verbose_name_plural = '점수 산출 결과'
        ordering = ['-final_score', 'user__employee_no']
        constraints = [
            models.UniqueConstraint(fields=['cycle', 'user'], name='uniq_score_cycle_user'),
            models.CheckConstraint(
                condition=models.Q(final_score__gte=0) & models.Q(final_score__lte=100),
                name='score_final_range',
            ),
        ]
        indexes = [models.Index(fields=['cycle', 'department'])]

    def __str__(self):
        return f'{self.user.name} · {self.final_score}'
