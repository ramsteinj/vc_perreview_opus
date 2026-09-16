from django.db import models


class TimeStampedModel(models.Model):
    """생성/수정 시각을 공통으로 제공하는 추상 베이스 모델."""

    created_at = models.DateTimeField('생성일시', auto_now_add=True)
    updated_at = models.DateTimeField('수정일시', auto_now=True)

    class Meta:
        abstract = True
