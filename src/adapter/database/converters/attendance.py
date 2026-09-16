from adapter.database.models import AttendanceModel
from domain.attendance.entity import Attendance
from domain.vo.attendance_status import AttendanceStatus


def attendance_to_domain(model: AttendanceModel) -> Attendance:
    return Attendance(
        id=model.id,
        student_id=model.student_id,
        lesson_id=model.lesson_id,
        status=AttendanceStatus(model.status),
        version=model.version,
        created_by_provider=model.created_by_provider,
        created_by_external_user_id=model.created_by_external_user_id,
        updated_by_provider=model.updated_by_provider,
        updated_by_external_user_id=model.updated_by_external_user_id,
        comment=model.comment,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )
