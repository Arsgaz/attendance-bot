from zoneinfo import ZoneInfo

from dishka import Provider, Scope, provide

from application.command.create_attendance_request import CreateAttendanceRequestHandler
from application.command.decide_attendance_request import DecideAttendanceRequestHandler
from application.command.mark_attendance import MarkAttendanceHandler
from application.command.notify_attendance_request import NotifyAttendanceRequestHandler
from application.command.register_student import RegisterStudentHandler
from application.command.set_student_starosta import SetStudentStarostaHandler
from application.command.unlink_registration import UnlinkRegistrationHandler
from application.command.unlink_student_accounts import UnlinkStudentAccountsHandler
from application.command.update_own_attendance import UpdateOwnAttendanceHandler
from application.query import (
    CheckOwnerAccessHandler,
    GetMyRegistrationHandler,
    ListActiveRegistrationsHandler,
    ListAttendanceDatesHandler,
    ListAvailableStudentsHandler,
    ListLessonsForDateHandler,
    ListLinkedStudentsHandler,
    ListManagedStudentsHandler,
    ListMyAttendanceHandler,
    ListStarostaExternalIdsHandler,
    ListStudentAttendanceHandler,
)
from application.query.get_bonus_balance import GetBonusBalanceHandler
from application.query.list_pending_attendance_requests import ListPendingAttendanceRequestsHandler
from config.settings import Settings
from port.clock import Clock
from port.repositories.attendance import AttendanceRepository


class InteractorProvider(Provider):
    """Build application use cases from ports supplied by infrastructure providers."""

    scope = Scope.REQUEST

    mark_attendance = provide(MarkAttendanceHandler)
    notify_attendance_request = provide(NotifyAttendanceRequestHandler)
    register_student = provide(RegisterStudentHandler)
    set_student_starosta = provide(SetStudentStarostaHandler)
    unlink_registration = provide(UnlinkRegistrationHandler)
    unlink_student_accounts = provide(UnlinkStudentAccountsHandler)
    update_own_attendance = provide(UpdateOwnAttendanceHandler)
    create_attendance_request = provide(CreateAttendanceRequestHandler)
    decide_attendance_request = provide(DecideAttendanceRequestHandler)
    list_pending_attendance_requests = provide(ListPendingAttendanceRequestsHandler)
    check_owner_access = provide(CheckOwnerAccessHandler)
    get_my_registration = provide(GetMyRegistrationHandler)
    list_available_students = provide(ListAvailableStudentsHandler)
    list_attendance_dates = provide(ListAttendanceDatesHandler)
    list_active_registrations = provide(ListActiveRegistrationsHandler)
    list_linked_students = provide(ListLinkedStudentsHandler)
    list_managed_students = provide(ListManagedStudentsHandler)
    list_lessons_for_date = provide(ListLessonsForDateHandler)
    list_my_attendance = provide(ListMyAttendanceHandler)
    list_starosta_external_ids = provide(ListStarostaExternalIdsHandler)
    list_student_attendance = provide(ListStudentAttendanceHandler)

    @provide
    def get_bonus_balance(
        self,
        attendance: AttendanceRepository,
        clock: Clock,
        timezone: ZoneInfo,
        settings: Settings,
    ) -> GetBonusBalanceHandler:
        return GetBonusBalanceHandler(
            attendance=attendance,
            clock=clock,
            timezone=timezone,
            weekly_limit=settings.bonus_weekly_limit,
        )
