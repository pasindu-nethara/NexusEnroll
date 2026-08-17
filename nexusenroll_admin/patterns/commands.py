"""
patterns/commands.py

Role: PATTERNS — Command (behavioral design pattern).

Every admin action (create course, deactivate account, force-enrol,
delete course, etc.) is wrapped in a Command object with a uniform
execute() method. This:

  1. Decouples the invoker (AdminFacade / CLI) from the concrete
     service logic behind each action — the invoker just calls
     command.execute(), never knowing which service is involved.
  2. Enables the audit log required by the assignment: every
     Command.execute() call appends one AuditLogEntry describing what
     happened, who did it, and whether it succeeded — regardless of
     which concrete command ran. New commands automatically get audit
     logging for free just by extending AdminCommand (Open/Closed:
     add a new command class, no existing code changes).

Each concrete command stores only the data and service reference it
needs, then performs exactly one admin action in execute().
"""

from abc import ABC, abstractmethod
from datetime import datetime, timezone

from data.entities import AuditLogEntry
from data.repositories import AuditLogRepository


class AdminCommand(ABC):
    """
    Abstract base for all admin action commands.

    Concrete subclasses implement _do_execute() with their specific
    logic; execute() wraps that call with uniform audit logging and
    error handling so every command behaves consistently for the
    invoker (AdminFacade).
    """

    def __init__(self, audit_log_repo: AuditLogRepository, actor: str):
        self._audit_log_repo = audit_log_repo
        self._actor = actor

    @abstractmethod
    def _do_execute(self):
        """Perform the actual action. Subclasses implement this. May raise ValueError."""
        ...

    @abstractmethod
    def command_name(self) -> str:
        """Short human-readable name for the audit log, e.g. 'CreateCourse'."""
        ...

    def execute(self):
        """
        Template method: run _do_execute(), then always record an
        audit log entry (success or failure) before returning /
        re-raising. This is the uniform execute() interface required
        by the assignment for the action/audit log.
        """
        timestamp = datetime.now(timezone.utc).isoformat()
        try:
            result = self._do_execute()
            self._audit_log_repo.add(AuditLogEntry(
                command_name=self.command_name(),
                actor=self._actor,
                details=self._details_on_success(result),
                success=True,
                timestamp=timestamp,
            ))
            return result
        except Exception as exc:
            self._audit_log_repo.add(AuditLogEntry(
                command_name=self.command_name(),
                actor=self._actor,
                details=f"FAILED: {exc}",
                success=False,
                timestamp=timestamp,
            ))
            raise

    def _details_on_success(self, result) -> str:
        """Override to customise the audit-log detail string; default is generic."""
        return f"{self.command_name()} completed successfully."


# ============================================================
# Concrete Commands
# ============================================================

class CreateCourseCommand(AdminCommand):
    """Command wrapping CourseService.create_course()."""

    def __init__(self, audit_log_repo, actor, course_service, course):
        super().__init__(audit_log_repo, actor)
        self._course_service = course_service
        self._course = course

    def command_name(self) -> str:
        return "CreateCourse"

    def _do_execute(self):
        self._course_service.create_course(self._course)
        return self._course

    def _details_on_success(self, result) -> str:
        return f"Created course {result.code} ({result.course_id})."


class DeleteCourseCommand(AdminCommand):
    """Command wrapping CourseService.delete_course()."""

    def __init__(self, audit_log_repo, actor, course_service, course_id):
        super().__init__(audit_log_repo, actor)
        self._course_service = course_service
        self._course_id = course_id

    def command_name(self) -> str:
        return "DeleteCourse"

    def _do_execute(self):
        return self._course_service.delete_course(self._course_id)

    def _details_on_success(self, result) -> str:
        return f"Deleted course {result.code} ({result.course_id})."


class DeactivateAccountCommand(AdminCommand):
    """
    Command wrapping account deactivation for either a student or
    faculty member. `account_type` selects which AccountService method
    to call (student vs faculty), keeping this one command reusable
    for both (DRY) rather than writing two nearly-identical commands.
    """

    def __init__(self, audit_log_repo, actor, account_service, account_type: str, account_id: str):
        super().__init__(audit_log_repo, actor)
        if account_type not in ("student", "faculty"):
            raise ValueError("account_type must be 'student' or 'faculty'")
        self._account_service = account_service
        self._account_type = account_type
        self._account_id = account_id

    def command_name(self) -> str:
        return "DeactivateAccount"

    def _do_execute(self):
        if self._account_type == "student":
            return self._account_service.deactivate_student(self._account_id)
        return self._account_service.deactivate_faculty(self._account_id)

    def _details_on_success(self, result) -> str:
        return f"Deactivated {self._account_type} account {self._account_id}."


class OverrideEnrolmentCommand(AdminCommand):
    """Command wrapping OverrideService.force_enrol()."""

    def __init__(self, audit_log_repo, actor, override_service, student_id, course_id):
        super().__init__(audit_log_repo, actor)
        self._override_service = override_service
        self._student_id = student_id
        self._course_id = course_id

    def command_name(self) -> str:
        return "OverrideEnrolment"

    def _do_execute(self):
        return self._override_service.force_enrol(self._student_id, self._course_id)

    def _details_on_success(self, result) -> str:
        return f"Force-enrolled student {self._student_id} into {result.code}."
