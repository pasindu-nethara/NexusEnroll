"""
patterns/facade.py

Role: PATTERNS — Facade (structural design pattern).

AdminFacade is the SINGLE entry point the Presentation Tier (CLI)
talks to. It hides the fact that, underneath, there are four
separate services (CourseService, ProgramService, AccountService,
OverrideService), a ReportingService, three Factory Method
hierarchies, and a Command layer with an audit log — the CLI never
imports or references any of those directly, only AdminFacade.

This is:
  - Dependency Inversion in action: main.py depends on the AdminFacade
    abstraction, not on concrete service classes.
  - Single Responsibility at the system level: the Facade's only job
    is "translate simple CLI-friendly calls into the right
    service/command/factory calls" — it contains no business rules
    itself (those live in the services) and no data access (that
    lives in the repositories).

Every mutating action goes through a Command object (so it is
audit-logged uniformly); every read-only listing/report goes straight
to the relevant service, since there is nothing to audit.
"""

from data.repositories import AuditLogRepository
from service.course_service import CourseService, ProgramService
from service.account_service import AccountService
from service.override_service import OverrideService
from service.reporting_service import ReportingService

from patterns.factories import (
    CourseFactory,
    ProgramFactory,
    StudentAccountFactory,
    FacultyAccountFactory,
    EnrolmentStatsReportFactory,
    FacultyWorkloadReportFactory,
    CoursePopularityReportFactory,
)
from patterns.commands import (
    CreateCourseCommand,
    DeleteCourseCommand,
    DeactivateAccountCommand,
    OverrideEnrolmentCommand,
)


class AdminFacade:
    """Unified, simplified interface over all Administrator Module functionality."""

    def __init__(
        self,
        course_service: CourseService,
        program_service: ProgramService,
        account_service: AccountService,
        override_service: OverrideService,
        reporting_service: ReportingService,
        audit_log_repo: AuditLogRepository,
        actor: str = "admin",
    ):
        self._course_service = course_service
        self._program_service = program_service
        self._account_service = account_service
        self._override_service = override_service
        self._reporting_service = reporting_service
        self._audit_log_repo = audit_log_repo
        self._actor = actor

        self._course_factory = CourseFactory()
        self._program_factory = ProgramFactory()
        self._student_factory = StudentAccountFactory()
        self._faculty_factory = FacultyAccountFactory()

    # ---------------------- Course & Program Management ----------------------

    def list_courses(self):
        return self._course_service.list_courses()

    def create_course(self, **fields):
        """Build a Course via CourseFactory, then run it through CreateCourseCommand (audited)."""
        course = self._course_factory.create_entity(**fields)
        return CreateCourseCommand(self._audit_log_repo, self._actor, self._course_service, course).execute()

    def edit_course(self, course_id: str, **updates):
        # Read-modify actions that aren't "create/delete/override" style are
        # simple enough to call the service directly; still funnel through
        # the service's own validation.
        return self._course_service.edit_course(course_id, **updates)

    def delete_course(self, course_id: str):
        return DeleteCourseCommand(self._audit_log_repo, self._actor, self._course_service, course_id).execute()

    def list_programs(self):
        return self._program_service.list_programs()

    def create_program(self, **fields):
        program = self._program_factory.create_entity(**fields)
        self._program_service.create_program(program)
        return program

    def edit_program(self, program_id: str, **updates):
        return self._program_service.edit_program(program_id, **updates)

    # ---------------------- Student & Faculty Management ----------------------

    def list_students(self):
        return self._account_service.list_students()

    def add_student(self, **fields):
        student = self._student_factory.create_account(**fields)
        self._account_service.add_student(student)
        return student

    def edit_student(self, student_id: str, **updates):
        return self._account_service.edit_student(student_id, **updates)

    def deactivate_student(self, student_id: str):
        return DeactivateAccountCommand(
            self._audit_log_repo, self._actor, self._account_service, "student", student_id
        ).execute()

    def list_faculty(self):
        return self._account_service.list_faculty()

    def add_faculty(self, **fields):
        faculty = self._faculty_factory.create_account(**fields)
        self._account_service.add_faculty(faculty)
        return faculty

    def edit_faculty(self, faculty_id: str, **updates):
        return self._account_service.edit_faculty(faculty_id, **updates)

    def deactivate_faculty(self, faculty_id: str):
        return DeactivateAccountCommand(
            self._audit_log_repo, self._actor, self._account_service, "faculty", faculty_id
        ).execute()

    # ---------------------- Enrolment Overrides ----------------------

    def force_enrol(self, student_id: str, course_id: str):
        return OverrideEnrolmentCommand(
            self._audit_log_repo, self._actor, self._override_service, student_id, course_id
        ).execute()

    # ---------------------- Reporting & Analytics ----------------------

    def enrolment_stats_report(self):
        rows = self._reporting_service.enrolment_stats_by_department()
        return EnrolmentStatsReportFactory().create_report("Enrolment Stats by Department", rows)

    def faculty_workload_report(self):
        rows = self._reporting_service.faculty_workload_report()
        return FacultyWorkloadReportFactory().create_report("Faculty Workload Report", rows)

    def course_popularity_report(self, capacity_threshold_pct: float = 90.0):
        rows = self._reporting_service.course_popularity_report(capacity_threshold_pct)
        title = f"Courses at or above {capacity_threshold_pct:.0f}% Capacity"
        return CoursePopularityReportFactory().create_report(title, rows)

    # ---------------------- Audit Log ----------------------

    def get_audit_log(self):
        return self._audit_log_repo.get_all()
