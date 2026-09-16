# 06. 점수 계산 규칙

> 모든 계산은 `Decimal`로 수행한다. 부동소수점(`float`) 연산을 사용하지 않는다.
> 구현 위치: `apps/evaluations/services/scoring.py`

## 1. 계산 단계 요약

```
① 평가지 환산 점수   각 EvaluationResponse → 0~100
        ↓
② 개인 평가 점수     1차/2차 평가지 가중 결합 → 0~100
        ↓
③ 부서 성과 점수     부서 평가지 결합 → 0~100
        ↓
④ 부서 가감값        (부서 점수 - 기준점) × 계수, 상·하한 적용
        ↓
⑤ 최종 점수          clamp(개인 점수 + 부서 가감, 0, 100)
```

## 2. ① 평가지 환산 점수 (Sheet Score)

평가지 한 장(`EvaluationResponse`)의 점수를 0~100으로 환산한다.

각 항목의 답변 점수를 백분율로 정규화한 뒤, 가중치로 가중 평균한다.

```
item_pct(i)  = answer.score(i) / item.max_score(i) × 100

                Σ ( item_pct(i) × weight(i) )
sheet_score = ───────────────────────────────
                       Σ weight(i)
```

- `i`는 해당 평가지의 **답변이 존재하고 `score`가 `null`이 아닌 활성 항목**만 포함한다.
- 제출된(`SUBMITTED`) 평가지는 모든 활성 항목에 답변이 있으므로 `Σ weight(i) = 100`이다.
  분모를 `Σ weight(i)`로 두는 이유는 항목이 비활성화된 예외 상황에서도 정규화가
  깨지지 않게 하기 위함이다.
- `Σ weight(i) == 0`이면 `sheet_score = None`으로 취급한다 (계산 불가).

**예시** (5점 척도, 3개 항목)

| 항목 | 점수 | max | item_pct | weight |
|------|------|-----|----------|--------|
| 업무성과 | 4 | 5 | 80.00 | 50 |
| 협업     | 5 | 5 | 100.00 | 30 |
| 태도     | 3 | 5 | 60.00 | 20 |

```
sheet_score = (80×50 + 100×30 + 60×20) / 100
            = (4000 + 3000 + 1200) / 100
            = 82.00
```

## 3. ② 개인 평가 점수 (Individual Score)

1차 평가지와 2차 평가지를 회차에 설정된 비율로 결합한다.

**2차 평가자가 지정되어 있고 2차 평가지가 제출된 경우:**

```
individual_score = primary_score  × (cycle.primary_weight  / 100)
                 + secondary_score × (cycle.secondary_weight / 100)
```

**2차 평가자가 없거나, 지정되었으나 제출되지 않은 경우:**

```
individual_score = primary_score
```

> 2차 평가는 선택 사항이므로, 미제출을 0점으로 처리하지 않는다.
> 1차 점수를 100% 반영해 피평가자가 불이익을 받지 않게 한다.

**1차 평가지가 제출되지 않은 경우:** `individual_score`를 산출하지 않는다.
해당 피평가자는 `ScoreResult`를 생성하지 않고, 산출 결과에 "미산출" 사유와 함께
집계한다. (관리자가 현황 화면에서 미제출자를 확인하고 독려한 뒤 재산출)

**예시** (`primary_weight=70`, `secondary_weight=30`)

```
primary_score   = 82.00
secondary_score = 90.00
individual_score = 82.00 × 0.70 + 90.00 × 0.30
                 = 57.40 + 27.00
                 = 84.40
```

## 4. ③ 부서 성과 점수 (Department Score)

`target_type=DEPARTMENT`인 평가지에 대해 **①②와 동일한 방식**을 적용한다.
즉 부서용 평가 항목으로 평가지 환산 점수를 구하고, 1차/2차 부서 평가자의
점수를 `primary_weight`/`secondary_weight`로 결합한다.

```
department_score = dept_primary_score   × (primary_weight  / 100)
                 + dept_secondary_score × (secondary_weight / 100)
```

부서 평가지가 제출되지 않은 부서는 `department_score = None`이며,
소속 직원의 **부서 가감값은 0**이 된다 (§5 참조).

**소속 부서 판정:** 피평가자의 `user.department`를 기준으로 한다.
상위 부서만 평가된 경우 자기 부서에 평가가 없으면 **가장 가까운 상위 부서의
점수를 상속**한다 (`parent`를 따라 올라가며 최초로 발견되는 점수 사용).

## 5. ④ 부서 가감값 (Department Adjustment)

부서 성과 점수를 기준점과 비교해 편차에 계수를 곱하고, 상·하한을 적용한다.

```
raw_adjustment = (department_score - cycle.dept_baseline_score) × cycle.dept_adjust_factor

department_adjustment = clamp(raw_adjustment,
                              -cycle.dept_adjust_limit,
                              +cycle.dept_adjust_limit)
```

`department_score`가 `None`이면 `department_adjustment = 0`.

**기본 파라미터** (`EvaluationCycle` 필드, 회차별 변경 가능)

| 파라미터 | 기본값 | 의미 |
|----------|--------|------|
| `dept_baseline_score` | 70.00 | 이 점수를 넘으면 가산, 밑돌면 감산 |
| `dept_adjust_factor` | 0.20 | 편차의 20%를 반영 |
| `dept_adjust_limit` | 10.00 | 가감 폭을 ±10점으로 제한 |

> **이 기본값들은 합리적 초기값이며 업무 규정에 따라 조정되어야 한다.**
> 실제 인사 규정이 확정되면 회차 생성 시 관리자가 값을 설정한다.

**예시**

| 부서 점수 | 편차 | raw | 최종 가감 |
|-----------|------|-----|-----------|
| 90.00 | +20.00 | +4.00 | **+4.00** |
| 70.00 | 0 | 0 | **0.00** |
| 45.00 | -25.00 | -5.00 | **-5.00** |
| 100.00 | +30.00 | +6.00 | **+6.00** |
| 0.00 | -70.00 | -14.00 | **-10.00** (하한 적용) |

## 6. ⑤ 최종 점수 (Final Score)

```
final_score = clamp(individual_score + department_adjustment, 0, 100)
```

**예시**

```
individual_score      = 84.40
department_adjustment = +4.00
final_score           = clamp(88.40, 0, 100) = 88.40
```

경계 사례:

```
individual_score = 98.00, adjustment = +4.00  → clamp(102.00) = 100.00
individual_score =  3.00, adjustment = -5.00  → clamp(-2.00)  =   0.00
```

## 7. 반올림 규칙

- 중간 계산(`item_pct`, `sheet_score`, `individual_score`, `department_score`,
  `department_adjustment`)은 **소수 둘째 자리에서 `ROUND_HALF_UP` 반올림**한다.
- 최종 점수도 동일하게 소수 둘째 자리까지 유지한다.
- 저장 타입은 `DecimalField(max_digits=6, decimal_places=2)`.

```python
from decimal import Decimal, ROUND_HALF_UP

def q2(value: Decimal) -> Decimal:
    return value.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
```

## 8. 산출 실행

| 트리거 | 동작 |
|--------|------|
| `POST /api/admin/cycles/{id}/calculate/` | 해당 회차 전체 재산출 |
| 회차 상태를 `CLOSED`로 전이 | 자동 산출 실행 |

- 산출은 **멱등(idempotent)** 하다. 몇 번을 실행해도 같은 입력에 같은 결과를 낸다.
- 결과는 `ScoreResult`에 `update_or_create`로 반영한다.
- 전체 산출은 단일 트랜잭션으로 처리한다. 일부 실패 시 전체 롤백.
- 산출 대상: 해당 회차에 `target_type=EMPLOYEE` 배정이 있는 모든 피평가자.

### 산출 결과 요약 응답

```json
{
  "cycle_id": 3,
  "calculated_at": "2026-09-16T10:22:31Z",
  "total_targets": 128,
  "calculated": 121,
  "skipped": 7,
  "skipped_reasons": [
    { "user_id": 45, "employee_no": "20210133", "name": "김철수",
      "reason": "PRIMARY_NOT_SUBMITTED" }
  ]
}
```

`skipped_reasons`의 `reason` 값: `PRIMARY_NOT_SUBMITTED`, `NO_ASSIGNMENT`,
`NO_ACTIVE_ITEMS`, `ZERO_WEIGHT_SUM`.

## 9. 테스트 케이스 (필수)

`apps/evaluations/tests/test_scoring.py`에 최소한 아래를 포함한다.

| # | 시나리오 | 기대 결과 |
|---|----------|-----------|
| 1 | 3개 항목 가중 평균 (§2 예시) | `sheet_score == 82.00` |
| 2 | 1차만 제출, 2차 평가자 없음 | `individual_score == primary_score` |
| 3 | 1차만 제출, 2차 평가자 지정됨 (미제출) | `individual_score == primary_score` |
| 4 | 1차 + 2차 모두 제출 | 70:30 가중 결합 |
| 5 | 부서 점수 90, 기준 70, 계수 0.2 | `adjustment == +4.00` |
| 6 | 부서 점수 0, 하한 ±10 | `adjustment == -10.00` |
| 7 | 부서 평가지 미제출 | `adjustment == 0`, `department_score is None` |
| 8 | 개인 98 + 가감 +4 | `final_score == 100.00` (상한) |
| 9 | 개인 3 + 가감 -5 | `final_score == 0.00` (하한) |
| 10 | 1차 미제출 | `ScoreResult` 미생성, `skipped` 집계 |
| 11 | 같은 입력으로 2회 산출 | 결과 동일, 레코드 중복 없음 (멱등성) |
| 12 | 부서 미평가 + 상위 부서 평가 존재 | 상위 부서 점수 상속 |
