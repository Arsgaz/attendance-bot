from aiogram.filters.callback_data import CallbackData


class SelectStudentCallback(CallbackData, prefix="student"):
    student_id: str


class ConfirmRegistrationCallback(CallbackData, prefix="register"):
    student_id: str


class CancelRegistrationCallback(CallbackData, prefix="register_cancel"):
    pass


class AttendanceDateCallback(CallbackData, prefix="attendance_date"):
    value: str


class AttendanceLessonCallback(CallbackData, prefix="attendance_lesson"):
    lesson_id: str


class AttendanceStatusCallback(CallbackData, prefix="attendance_status"):
    lesson_id: str
    status: str


class ConfirmAttendanceCallback(CallbackData, prefix="attendance_confirm"):
    lesson_id: str
    status: str


class AttendanceNavigationCallback(CallbackData, prefix="attendance_nav"):
    action: str


class ManageAttendanceCallback(CallbackData, prefix="manage_mark"):
    attendance_id: str


class EditAttendanceCallback(CallbackData, prefix="edit_mark"):
    attendance_id: str
    status: str


class DeleteAttendanceCallback(CallbackData, prefix="delete_mark"):
    attendance_id: str


class ConfirmDeleteAttendanceCallback(CallbackData, prefix="confirm_delete"):
    attendance_id: str


class AttendanceRequestDecisionCallback(CallbackData, prefix="attendance_request_decide"):
    request_id: str
    approve: int


class UnlinkAccountCallback(CallbackData, prefix="unlink_account"):
    registration_id: str


class ConfirmUnlinkAccountCallback(CallbackData, prefix="confirm_unlink_account"):
    registration_id: str


class StudentAccountsCallback(CallbackData, prefix="student_accounts"):
    student_id: str


class UnlinkAllStudentAccountsCallback(CallbackData, prefix="unlink_all_accounts"):
    student_id: str


class ConfirmUnlinkAllStudentAccountsCallback(CallbackData, prefix="confirm_unlink_all"):
    student_id: str


class ManageStudentRoleCallback(CallbackData, prefix="manage_role"):
    student_id: str


class SetStudentRoleCallback(CallbackData, prefix="set_role"):
    student_id: str
    enabled: int


class StudentAttendanceCallback(CallbackData, prefix="student_att"):
    student_id: str


class StudentAttendanceWeekCallback(CallbackData, prefix="student_att_w"):
    student_id: str
    week_start: str
