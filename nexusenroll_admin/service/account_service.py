"""
service/account_service.py

Role: SERVICE TIER — Student & Faculty account management business logic.

AccountService handles both Student and Faculty accounts. They share
identical lifecycle behaviour (add/edit/deactivate), so rather than
duplicating near-identical code in two classes (violating DRY), this
single service works against whichever repository (StudentRepository
or FacultyRepository) is passed to each method — both repositories
already share the same shape (add/update/set_status) by design.

Deactivation triggers a NotificationService call, satisfying the
requirement that admin actions with system-wide effects hook into
the (external) Notification subsystem via its interface.
"""

from data.entities import AccountStatus
from data.repositories import StudentRepository, FacultyRepository
from service.notification_service import NotificationService


class AccountService:
    """Business logic for managing student and faculty accounts."""

    def __init__(
        self,
        student_repo: StudentRepository,
        faculty_repo: FacultyRepository,
        notification_service: NotificationService,
    ):
        self._student_repo = student_repo
        self._faculty_repo = faculty_repo
        self._notifier = notification_service

    # ---------------------------- Students ----------------------------

    def list_students(self) -> list:
        return self._student_repo.get_all()

    def add_student(self, student) -> None:
        if self._student_repo.get_by_id(student.student_id) is not None:
            raise ValueError(f"Student ID '{student.student_id}' already exists.")
        self._student_repo.add(student)

    def edit_student(self, student_id: str, **updates):
        student = self._student_repo.get_by_id(student_id)
        if student is None:
            raise ValueError(f"Student '{student_id}' not found.")
        for field_name in ("name", "email", "program_id"):
            if field_name in updates:
                setattr(student, field_name, updates[field_name])
        self._student_repo.update(student)
        return student

    def deactivate_student(self, student_id: str) -> bool:
        """
        Deactivate a student account and notify them (extension point
        call to NotificationService — real implementation is out of
        scope for this module).
        """
        student = self._student_repo.get_by_id(student_id)
        if student is None:
            raise ValueError(f"Student '{student_id}' not found.")
        ok = self._student_repo.set_status(student_id, AccountStatus.INACTIVE)
        if ok:
            self._notifier.notify(student_id, "Your account has been deactivated by an administrator.")
        return ok

    # ---------------------------- Faculty ----------------------------

    def list_faculty(self) -> list:
        return self._faculty_repo.get_all()

    def add_faculty(self, faculty) -> None:
        if self._faculty_repo.get_by_id(faculty.faculty_id) is not None:
            raise ValueError(f"Faculty ID '{faculty.faculty_id}' already exists.")
        self._faculty_repo.add(faculty)

    def edit_faculty(self, faculty_id: str, **updates):
        faculty = self._faculty_repo.get_by_id(faculty_id)
        if faculty is None:
            raise ValueError(f"Faculty '{faculty_id}' not found.")
        for field_name in ("name", "email", "department"):
            if field_name in updates:
                setattr(faculty, field_name, updates[field_name])
        self._faculty_repo.update(faculty)
        return faculty

    def deactivate_faculty(self, faculty_id: str) -> bool:
        """Deactivate a faculty account and notify them."""
        faculty = self._faculty_repo.get_by_id(faculty_id)
        if faculty is None:
            raise ValueError(f"Faculty '{faculty_id}' not found.")
        ok = self._faculty_repo.set_status(faculty_id, AccountStatus.INACTIVE)
        if ok:
            self._notifier.notify(faculty_id, "Your account has been deactivated by an administrator.")
        return ok
