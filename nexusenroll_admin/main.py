"""
main.py

Role: Composition root / entry point for the NexusEnroll
Administrator Module.

This file is the ONLY place that wires concrete implementations to
abstract interfaces (dependency injection by hand): it constructs
the in-memory repositories, seeds mock data, builds the services on
top of the repositories, builds the AdminFacade on top of the
services, and finally hands the Facade to the CLI. This keeps every
other file honestly decoupled — none of them import a concrete class
they don't themselves construct.

3-Tier wiring performed here:
    Data Tier          -> repositories + mock data
    Service Tier        -> services (built on repository abstractions)
    Patterns             -> AdminFacade (built on services)
    Presentation Tier   -> AdminCLI (built on AdminFacade only)

Run with:  python main.py
"""

from data.repositories import (
    InMemoryCourseRepository,
    InMemoryProgramRepository,
    InMemoryStudentRepository,
    InMemoryFacultyRepository,
    InMemoryAuditLogRepository,
)
from data.mock_data import seed_mock_data

from service.course_service import CourseService, ProgramService
from service.account_service import AccountService
from service.override_service import OverrideService
from service.reporting_service import ReportingService
from service.notification_service import ConsoleNotificationService

from patterns.facade import AdminFacade
from presentation.cli import AdminCLI


def build_facade() -> AdminFacade:
    """Construct and wire the full Administrator Module stack, seeded with mock data."""

    # --- Data Tier ---
    course_repo = InMemoryCourseRepository()
    program_repo = InMemoryProgramRepository()
    student_repo = InMemoryStudentRepository()
    faculty_repo = InMemoryFacultyRepository()
    audit_log_repo = InMemoryAuditLogRepository()

    seed_mock_data(course_repo, program_repo, student_repo, faculty_repo)

    # --- Extension point (Notification subsystem stand-in) ---
    notification_service = ConsoleNotificationService()

    # --- Service Tier ---
    course_service = CourseService(course_repo)
    program_service = ProgramService(program_repo)
    account_service = AccountService(student_repo, faculty_repo, notification_service)
    override_service = OverrideService(course_repo, student_repo, notification_service)
    reporting_service = ReportingService(course_repo, student_repo, faculty_repo)

    # --- Facade (Patterns layer) ---
    return AdminFacade(
        course_service=course_service,
        program_service=program_service,
        account_service=account_service,
        override_service=override_service,
        reporting_service=reporting_service,
        audit_log_repo=audit_log_repo,
        actor="admin",
    )


def main():
    facade = build_facade()
    cli = AdminCLI(facade)
    cli.run()


if __name__ == "__main__":
    main()


# ============================================================================
# CLOSING SUMMARY — Integration with the Student and Faculty Modules
# ============================================================================
#
# This Administrator Module is one of three modules in the full NexusEnroll
# SOA system (Student, Faculty, Administrator), each owned by a different
# team and each following the same 3-tier separation. Integration points:
#
# 1. Shared entity shapes (data/entities.py):
#    Course.capacity / Course.enrolled_count are exactly the fields the
#    Student Module's registration flow would check before confirming an
#    add ("capacity check"). When this Admin Module edits a course's
#    capacity or force-enrols a student, those same fields change — so in
#    the full system, all three modules would read/write ONE shared Course
#    table (or a Course microservice) rather than each keeping a private
#    copy, keeping the numbers the Student Module sees always current.
#
# 2. Repository interfaces as the seam for a shared data layer
#    (data/repositories.py):
#    Because every repository here is used only through its abstract base
#    class, the in-memory dict-backed implementations built for this demo
#    could be replaced by implementations backed by a real shared database
#    or by calls to a separate Course/Student/Faculty microservice's API —
#    without changing any Service Tier or Presentation Tier code in this
#    module. The Student and Faculty modules would depend on the same
#    abstractions (or their own read-only views of them).
#
# 3. NotificationService as the seam for the system-wide Notification
#    subsystem (service/notification_service.py):
#    force_enrol(), deactivate_student()/deactivate_faculty(), and
#    delete_course() all call NotificationService.notify() rather than
#    printing or emailing directly. In the full system, this interface
#    would be implemented once by a shared Notification microservice and
#    reused by all three modules — e.g. the same interface the Student
#    Module uses to notify a waitlisted student would be called here when
#    an admin frees up a seat by force-enrolling someone else out, or by
#    editing a course's capacity upward.
#
# 4. Faculty Module inputs feed Admin reporting:
#    ReportingService's faculty workload and enrolment-stats reports are
#    computed from Course/Student/Faculty data that, in the full system,
#    the Faculty Module's grade-submission and roster features would help
#    populate and keep current (e.g. enrolled_count changes as students
#    add/drop through the Student Module, not just through Admin actions).
#
# 5. Transaction Management as a wrapping seam:
#    OverrideService.force_enrol() performs its two related updates
#    (course.enrolled_count, student.enrolled_course_ids) as a single
#    method with no partial-state window, so the system-wide Transaction
#    Manager (not built here) could wrap this call — or any repository
#    method here — in a real database transaction without this module's
#    code needing to change.
#
# In short: every "seam" where this module touches the rest of NexusEnroll
# (shared entities, repository abstractions, NotificationService) is an
# interface, not a concrete implementation — which is what lets three
# separate teams build the Student, Faculty, and Administrator modules in
# parallel and integrate them later with minimal rework.
# ============================================================================
