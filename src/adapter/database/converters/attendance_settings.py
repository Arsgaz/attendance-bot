from adapter.database.models import AttendanceSettingsModel
from domain.attendance.settings import AttendanceSettings


def attendance_settings_to_domain(model: AttendanceSettingsModel) -> AttendanceSettings:
    return AttendanceSettings(
        timezone=model.timezone,
        bonus_weekly_limit=model.bonus_weekly_limit,
        allow_student_change=model.allow_student_change,
    )
