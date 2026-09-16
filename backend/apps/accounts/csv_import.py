"""사용자 CSV 일괄 등록 (specs/05-admin-features.md FR-A-02).

검증 실패 행은 사유와 함께 리포트하고 전체를 롤백한다.
부분 성공을 허용하지 않는 이유: 수십 건 중 일부만 들어간 상태를 관리자가
손으로 정리하는 것이 훨씬 번거롭다. 고치고 다시 올리는 편이 안전하다.
"""

import csv
import io
from datetime import date

from django.db import transaction

from apps.common.exceptions import DomainError

from .models import Department, Role, User
from .services import generate_temporary_password

# 스펙에 정의된 컬럼 순서
COLUMNS = ('employee_no', 'name', 'department_code', 'position', 'role', 'hired_on')
REQUIRED_COLUMNS = ('employee_no', 'name')

MAX_ROWS = 2000

# 한국어 Excel은 CP949로 저장하는 경우가 흔하다
ENCODINGS = ('utf-8-sig', 'utf-8', 'cp949')


class ImportFailed(DomainError):
    status_code = 400
    default_detail = '일부 행에 오류가 있어 등록하지 않았습니다.'
    default_code = 'IMPORT_VALIDATION_FAILED'


class ImportFileError(DomainError):
    status_code = 400
    default_detail = 'CSV 파일을 읽을 수 없습니다.'
    default_code = 'IMPORT_FILE_ERROR'


def decode(raw):
    """업로드된 바이트를 텍스트로 디코딩한다."""
    for encoding in ENCODINGS:
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise ImportFileError(
        'CSV 파일의 인코딩을 인식할 수 없습니다. UTF-8 또는 CP949로 저장해 주세요.',
        code='IMPORT_ENCODING_ERROR',
    )


def parse(text):
    """헤더를 검증하고 행 목록을 돌려준다."""
    reader = csv.DictReader(io.StringIO(text))

    if reader.fieldnames is None:
        raise ImportFileError('빈 파일입니다.', code='IMPORT_EMPTY_FILE')

    fieldnames = [(name or '').strip() for name in reader.fieldnames]
    missing = [c for c in REQUIRED_COLUMNS if c not in fieldnames]
    if missing:
        raise ImportFileError(
            f'필수 컬럼이 없습니다: {", ".join(missing)}',
            code='IMPORT_MISSING_COLUMNS',
            context={'required_columns': list(COLUMNS), 'found_columns': fieldnames},
        )

    rows = []
    for raw_row in reader:
        # 완전히 빈 줄은 조용히 건너뛴다 (Excel이 남기는 꼬리 행)
        if not any((value or '').strip() for value in raw_row.values()):
            continue
        rows.append({key: (raw_row.get(key) or '').strip() for key in fieldnames})
        if len(rows) > MAX_ROWS:
            raise ImportFileError(
                f'한 번에 등록할 수 있는 최대 건수({MAX_ROWS}건)를 초과했습니다.',
                code='IMPORT_TOO_MANY_ROWS',
            )

    if not rows:
        raise ImportFileError('등록할 데이터가 없습니다.', code='IMPORT_NO_ROWS')

    return rows


def _validate_row(row, line_no, departments, seen_numbers, existing_numbers):
    """행 하나를 검증한다. (정제된 값, 오류 목록)을 돌려준다."""
    errors = []

    employee_no = row.get('employee_no', '')
    name = row.get('name', '')

    if not employee_no:
        errors.append({'line': line_no, 'field': 'employee_no', 'message': '사번은 필수입니다.'})
    elif employee_no in existing_numbers:
        errors.append(
            {'line': line_no, 'field': 'employee_no', 'message': '이미 사용 중인 사번입니다.'}
        )
    elif employee_no in seen_numbers:
        errors.append(
            {
                'line': line_no,
                'field': 'employee_no',
                'message': f'파일 안에서 중복된 사번입니다 ({seen_numbers[employee_no]}행과 중복).',
            }
        )

    if not name:
        errors.append({'line': line_no, 'field': 'name', 'message': '성명은 필수입니다.'})

    department = None
    code = row.get('department_code', '')
    if code:
        department = departments.get(code)
        if department is None:
            errors.append(
                {
                    'line': line_no,
                    'field': 'department_code',
                    'message': f'존재하지 않는 부서코드입니다: {code}',
                }
            )
        elif not department.is_active:
            errors.append(
                {
                    'line': line_no,
                    'field': 'department_code',
                    'message': f'비활성 부서입니다: {code}',
                }
            )

    role = (row.get('role') or Role.EMPLOYEE).upper()
    if role not in Role.values:
        errors.append(
            {
                'line': line_no,
                'field': 'role',
                'message': f'권한은 {" 또는 ".join(Role.values)} 여야 합니다: {row.get("role")}',
            }
        )
        role = Role.EMPLOYEE

    hired_on = None
    raw_hired = row.get('hired_on', '')
    if raw_hired:
        try:
            hired_on = date.fromisoformat(raw_hired)
        except ValueError:
            errors.append(
                {
                    'line': line_no,
                    'field': 'hired_on',
                    'message': f'입사일은 YYYY-MM-DD 형식이어야 합니다: {raw_hired}',
                }
            )

    cleaned = {
        'employee_no': employee_no,
        'name': name,
        'department': department,
        'position': row.get('position', ''),
        'role': role,
        'hired_on': hired_on,
    }
    return cleaned, errors


@transaction.atomic
def bulk_import(raw_bytes):
    """CSV 바이트를 받아 사용자를 일괄 등록한다.

    오류가 하나라도 있으면 ImportFailed를 던져 전체를 롤백한다.
    성공 시 생성된 사용자와 임시 비밀번호를 돌려준다 (1회 노출).
    """
    rows = parse(decode(raw_bytes))

    departments = {d.code: d for d in Department.objects.all()}
    existing_numbers = set(User.objects.values_list('employee_no', flat=True))

    seen_numbers = {}
    cleaned_rows = []
    errors = []

    for index, row in enumerate(rows):
        line_no = index + 2  # 헤더가 1행
        cleaned, row_errors = _validate_row(
            row, line_no, departments, seen_numbers, existing_numbers
        )
        errors.extend(row_errors)

        if cleaned['employee_no']:
            seen_numbers.setdefault(cleaned['employee_no'], line_no)
        cleaned_rows.append((line_no, cleaned))

    if errors:
        raise ImportFailed(
            f'{len(errors)}건의 오류가 있어 등록하지 않았습니다. 수정 후 다시 올려주세요.',
            context={'error_count': len(errors), 'total_rows': len(rows), 'errors': errors},
        )

    created = []
    for _line_no, cleaned in cleaned_rows:
        password = generate_temporary_password()
        user = User.objects.create_user(password=password, **cleaned)
        created.append(
            {
                'id': user.id,
                'employee_no': user.employee_no,
                'name': user.name,
                'department_name': user.department.name if user.department else None,
                'role': user.role,
                'generated_password': password,
            }
        )

    return {'created_count': len(created), 'total_rows': len(rows), 'created': created}
