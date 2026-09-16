from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class AttendanceSettings:
    timezone: str
    bonus_weekly_limit: int
    allow_student_change: bool
