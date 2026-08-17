"""
nexusenroll/admin/composition.py

Role: Composition function for the Administrator module.

build_facade() is the ONLY place that wires concrete implementations
to abstract interfaces (dependency injection by hand): given the
shared, CSV-backed repositories and notification service constructed
by nexusenroll/system/app.py, it builds the Service Tier on top of
them, then the AdminFacade on top of the services. This keeps every
other file in this module honestly decoupled — none of them import a
concrete repository class they don't themselves receive as a
parameter.

3-Tier wiring performed here:
    Data Tier          -> repositories (constructed by the system composition root, passed in)
    Service Tier        -> services (built on repository abstractions)
    Patterns             -> AdminFacade (built on services)
    Presentation Tier   -> AdminCLI (built on AdminFacade only, by the caller)

There is deliberately no `if __name__ == "__main__":` entry point here
— NexusEnroll has exactly one entry point, nexusenroll/system/app.py
(run via the repository root's main.py), which imports build_facade()
as a library function.
"""

from nexusenroll.admin.data.repositories import (
    CourseRepository, ProgramRepository, StudentRepository, FacultyRepository, AuditLogRepository,
)
from nexusenroll.admin.service.course_service import CourseService, ProgramService
from nexusenroll.admin.service.account_service import AccountService
from nexusenroll.admin.service.override_service import OverrideService
from nexusenroll.admin.service.reporting_service import ReportingService
from nexusenroll.admin.service.notification_service import NotificationService

from nexusenroll.admin.patterns.facade import AdminFacade


def build_facade(
    course_repo: CourseRepository,
    program_repo: ProgramRepository,
    student_repo: StudentRepository,
    faculty_repo: FacultyRepository,
    audit_log_repo: AuditLogRepository,
    notification_service: NotificationService,
    actor: str = "admin",
) -> AdminFacade:
    """
    Construct and wire the full Administrator module stack on top of
    the given (shared) repositories and notification service.

    Every parameter is a repository/service ABSTRACTION — this
    function never constructs a concrete CSV-backed repository itself;
    that happens exactly once, in nexusenroll/system/app.py, and the
    SAME instances are also handed to the Student and Faculty
    services. That is what makes an admin's force-enrol or account
    edit immediately visible to the other two modules, and what
    eventually gets written to data/*.csv when the composition root
    calls save() on each repository.
    """

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
        actor=actor,
    )


# ============================================================================
# CLOSING SUMMARY — Integration with the Student and Faculty modules
# ============================================================================
#
# This Administrator module is one of three service modules in the full
# NexusEnroll SOA system (student, faculty, admin), each following the same
# 3-Tier internal split (data / service / patterns / presentation). Every
# seam below is a real, wired-up integration — see nexusenroll/system/app.py,
# the whole-system composition root.
#
# 1. Shared entity shapes, literally the same classes
#    (nexusenroll/common/domain.py, re-exported via admin/data/entities.py):
#    Course.capacity / Course.enrolled_count (a property derived from
#    Course.enrolled_student_ids) are exactly the fields the Student
#    service's registration flow checks before confirming an add ("capacity
#    check"). Because app.py hands this module's build_facade() the SAME
#    Course/Student/Faculty repository instances it also hands to the
#    Student and Faculty services, an admin editing a course's capacity or
#    force-enrolling a student updates the exact object the Student
#    service's next capacity check will read — and the exact row that ends
#    up in data/courses.csv.
#
# 2. Repository interfaces as the real seam for CSV persistence
#    (admin/data/repositories.py, re-exporting nexusenroll/common/repositories.py):
#    Because every repository here is used only through its abstract base
#    class, and build_facade() only ever receives repository instances as
#    parameters, the CSV-backed implementations used today could be swapped
#    for real database-backed implementations by changing only
#    nexusenroll/system/app.py's wiring — no Service Tier or Presentation
#    Tier code in this module changes.
#
# 3. NotificationService as the real seam for the system-wide Notification
#    subsystem (admin/service/notification_service.py, re-exporting
#    nexusenroll/common/notifications.py):
#    force_enrol(), deactivate_student()/deactivate_faculty() all call
#    NotificationService.notify() rather than printing or emailing
#    directly. app.py passes this module the SAME NotificationService
#    instance used by the Faculty module's advisor alerts.
#
# 4. Faculty module inputs feed Admin reporting, live:
#    ReportingService's faculty workload and enrolment-stats reports are
#    computed from the shared Course/Student/Faculty repositories. When the
#    Faculty module submits and approves grades, nexusenroll/system's
#    RegistrarBridge (an ESB subscriber) writes the result straight into
#    the shared StudentRepository, so this module's reports and the Student
#    module's own progress-tracking reflect it without any direct call
#    between the Faculty and Administrator modules.
#
# 5. Transaction Management as a wrapping seam:
#    OverrideService.force_enrol() performs its two related updates
#    (course.enrolled_student_ids, student.enrolled_course_ids) as a single
#    method with no partial-state window, so a real system-wide Transaction
#    Manager (not built here — out of scope per the assignment) could wrap
#    this call — or any repository method here — in a real database
#    transaction without this module's code needing to change.
# ============================================================================
