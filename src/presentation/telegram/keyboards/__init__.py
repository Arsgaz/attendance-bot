from presentation.telegram.keyboards.attendance import (
    attendance_confirmation_keyboard,
    attendance_dates_keyboard,
    attendance_status_keyboard,
    delete_attendance_confirmation_keyboard,
    excused_reason_keyboard,
    lessons_keyboard,
    manage_attendance_keyboard,
    my_attendance_keyboard,
)
from presentation.telegram.keyboards.common import main_menu_keyboard
from presentation.telegram.keyboards.registration import (
    registration_confirmation_keyboard,
    students_keyboard,
)
from presentation.telegram.keyboards.starosta import (
    active_registrations_keyboard,
    attendance_requests_keyboard,
    manage_student_role_keyboard,
    managed_students_keyboard,
    starosta_menu_keyboard,
    starosta_navigation_keyboard,
    student_accounts_keyboard,
    student_attendance_keyboard,
    unlink_account_confirmation_keyboard,
    unlink_all_confirmation_keyboard,
)

__all__ = [
    "active_registrations_keyboard",
    "attendance_confirmation_keyboard",
    "attendance_dates_keyboard",
    "attendance_status_keyboard",
    "attendance_requests_keyboard",
    "delete_attendance_confirmation_keyboard",
    "excused_reason_keyboard",
    "lessons_keyboard",
    "main_menu_keyboard",
    "manage_attendance_keyboard",
    "manage_student_role_keyboard",
    "managed_students_keyboard",
    "my_attendance_keyboard",
    "registration_confirmation_keyboard",
    "starosta_menu_keyboard",
    "starosta_navigation_keyboard",
    "student_attendance_keyboard",
    "student_accounts_keyboard",
    "unlink_all_confirmation_keyboard",
    "unlink_account_confirmation_keyboard",
    "students_keyboard",
]
