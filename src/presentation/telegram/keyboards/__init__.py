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
    attendance_request_decision_keyboard,
    bonus_requests_keyboard,
    starosta_menu_keyboard,
    starosta_navigation_keyboard,
)

__all__ = [
    "active_registrations_keyboard",
    "attendance_confirmation_keyboard",
    "attendance_dates_keyboard",
    "attendance_request_decision_keyboard",
    "attendance_status_keyboard",
    "bonus_requests_keyboard",
    "delete_attendance_confirmation_keyboard",
    "excused_reason_keyboard",
    "lessons_keyboard",
    "main_menu_keyboard",
    "manage_attendance_keyboard",
    "my_attendance_keyboard",
    "registration_confirmation_keyboard",
    "starosta_menu_keyboard",
    "starosta_navigation_keyboard",
    "students_keyboard",
]
