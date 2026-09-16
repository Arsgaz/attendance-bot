from datetime import date
from uuid import uuid4

from domain.vo.attendance_status import AttendanceStatus
from port.repositories.attendance import AttendanceView
from port.repositories.registration import StudentChoice
from presentation.telegram.callbacks import (
    CancelRegistrationCallback,
    ConfirmAttendanceCallback,
    ConfirmRegistrationCallback,
    SelectStudentCallback,
)
from presentation.telegram.keyboards import (
    attendance_dates_keyboard,
    main_menu_keyboard,
    my_attendance_keyboard,
    registration_confirmation_keyboard,
    students_keyboard,
)


def test_student_keyboard_contains_only_opaque_student_id() -> None:
    student = StudentChoice(id=uuid4(), full_name="Иванов Иван Иванович", subgroup="1")

    keyboard = students_keyboard([student])

    button = keyboard.inline_keyboard[0][0]
    assert button.text == "Иванов Иван Иванович · п/г 1"
    assert SelectStudentCallback.unpack(button.callback_data or "").student_id == str(student.id)


def test_confirmation_callbacks_fit_telegram_limit() -> None:
    student_id = str(uuid4())

    keyboard = registration_confirmation_keyboard(student_id)

    confirm_data = keyboard.inline_keyboard[0][0].callback_data or ""
    cancel_data = keyboard.inline_keyboard[0][1].callback_data or ""
    assert ConfirmRegistrationCallback.unpack(confirm_data).student_id == student_id
    assert CancelRegistrationCallback.unpack(cancel_data) == CancelRegistrationCallback()
    assert len(confirm_data.encode()) <= 64
    assert len(cancel_data.encode()) <= 64
    attendance_data = ConfirmAttendanceCallback(lesson_id=student_id, status="excused").pack()
    assert len(attendance_data.encode()) <= 64


def test_main_menu_contains_attendance_entries() -> None:
    keyboard = main_menu_keyboard()

    assert [[button.text for button in row] for row in keyboard.keyboard] == [
        ["Отметить посещение"],
        ["Мои отметки", "Лимит Б"],
    ]


def test_week_navigation_callbacks_can_be_packed() -> None:
    dates_keyboard = attendance_dates_keyboard(
        [date(2026, 9, 15)],
        newer_week_start=date(2026, 9, 21),
    )
    attendance_keyboard = my_attendance_keyboard(
        [
            AttendanceView(
                id=uuid4(),
                lesson_date=date(2026, 9, 15),
                subject="ИИС",
                subgroup="общая",
                status=AttendanceStatus.PRESENT,
            ),
        ],
        older_week_start=date(2026, 9, 7),
    )

    assert dates_keyboard.inline_keyboard[-2][0].callback_data
    assert attendance_keyboard.inline_keyboard[-1][0].callback_data
