"""평가 항목 로직 (specs/05-admin-features.md FR-A-04)."""

from django.db import transaction

from apps.common.exceptions import DomainError

from ..models import EvaluationItem


class ItemInUse(DomainError):
    default_detail = '응답이 존재하는 항목은 변경하거나 삭제할 수 없습니다.'
    default_code = 'ITEM_IN_USE'


# 응답이 생긴 뒤에는 점수의 의미가 바뀌므로 잠그는 필드
LOCKED_FIELDS = ('weight', 'max_score', 'target_type')


def ensure_item_mutable(item, changed_fields=None):
    """응답이 있는 항목의 가중치·척도 변경을 차단한다."""
    if not item.in_use:
        return
    if changed_fields is None:
        raise ItemInUse()
    if any(field in LOCKED_FIELDS for field in changed_fields):
        raise ItemInUse()


@transaction.atomic
def reorder_items(cycle, ordered_ids):
    """전달된 순서대로 order를 다시 매긴다."""
    items = {
        item.id: item for item in EvaluationItem.objects.filter(cycle=cycle, pk__in=ordered_ids)
    }
    updated = []
    for index, item_id in enumerate(ordered_ids, start=1):
        item = items.get(item_id)
        if item is None:
            continue
        item.order = index
        updated.append(item)

    EvaluationItem.objects.bulk_update(updated, ['order'])
    return len(updated)


@transaction.atomic
def clone_items(source_cycle, target_cycle, *, target_type=None, replace=False):
    """다른 회차의 평가 항목을 복제한다."""
    queryset = source_cycle.items.all()
    if target_type:
        queryset = queryset.filter(target_type=target_type)

    if replace:
        existing = target_cycle.items.all()
        if target_type:
            existing = existing.filter(target_type=target_type)
        for item in existing:
            ensure_item_mutable(item)
        existing.delete()

    existing_keys = set(target_cycle.items.values_list('target_type', 'code'))

    created = []
    skipped = []
    for source in queryset:
        if (source.target_type, source.code) in existing_keys:
            skipped.append({'code': source.code, 'target_type': source.target_type})
            continue
        created.append(
            EvaluationItem(
                cycle=target_cycle,
                target_type=source.target_type,
                code=source.code,
                title=source.title,
                description=source.description,
                weight=source.weight,
                max_score=source.max_score,
                order=source.order,
                is_active=source.is_active,
            )
        )

    EvaluationItem.objects.bulk_create(created)
    return {'created': len(created), 'skipped': skipped}
