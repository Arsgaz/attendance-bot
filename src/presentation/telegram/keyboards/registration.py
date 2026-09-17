from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from port.repositories.registration import StudentChoice
from presentation.telegram.callbacks import (
    CancelRegistrationCallback,
    ConfirmRegistrationCallback,
    SelectStudentCallback,
)


def students_keyboard(students: list[StudentChoice]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(
                text=f"{student.full_name} · п/г {student.subgroup}",
                callback_data=SelectStudentCallback(student_id=str(student.id)).pack(),
            )]
            for student in students
        ],
    )


def registration_confirmation_keyboard(student_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[
            InlineKeyboardButton(
                text="Да, это я",
                callback_data=ConfirmRegistrationCallback(student_id=student_id).pack(),
            ),
            InlineKeyboardButton(
                text="Назад",
                callback_data=CancelRegistrationCallback().pack(),
            ),
        ]],
    )
