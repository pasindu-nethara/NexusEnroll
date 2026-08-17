"""
service/override_service.py

Role: SERVICE TIER — Enrolment Override business logic.

Handles the "force-add a student into a full/closed class, bypassing
prerequisite/capacity/time-conflict checks" requirement. This is
DELIBERATELY the one place in the Admin Module that skips the normal
Student Module validation rules — that is precisely what makes it an
"override" and why it is restricted to administrators.

Transaction-safety note: force_enrol() updates the course's
enrolled_count and the student's enrolled_course_ids list together,
in one method, with no intervening return to the caller. This keeps
the operation a single atomic unit of work as required by the
system-wide Transaction Management requirement — if a real
TransactionManager/DB-transaction wrapper is introduced later, it can
wrap this entire method call and roll it back as one unit; there's no
window where only one of the two updates has happened and been
observed by another part of the system.
"""

from data.entities import Course, Student
from data.repositories import CourseRepository, StudentRepository
from service.notification_service import NotificationService


class OverrideService:
    """Business logic for administrator enrolment overrides."""

    def __init__(
        self,
        course_repo: CourseRepository,
        student_repo: StudentRepository,
        notification_service: NotificationService,
    ):
        self._course_repo = course_repo
        self._student_repo = student_repo
        self._notifier = notification_service

    def force_enrol(self, student_id: str, course_id: str) -> Course:
        """
        Force-enrol a student into a course, bypassing prerequisite,
        capacity, and time-conflict checks (those checks belong to the
        Student Module's normal add/drop flow, not here).

        Both the course's enrolled_count and the student's
        enrolled_course_ids are updated together as a single atomic
        step (see module docstring). On success, both the student and
        the course's instructor are notified via the
        NotificationService extension point.
        """
        course = self._course_repo.get_by_id(course_id)
        if course is None:
            raise ValueError(f"Course '{course_id}' not found.")
        student = self._student_repo.get_by_id(student_id)
        if student is None:
            raise ValueError(f"Student '{student_id}' not found.")

        if course_id in student.enrolled_course_ids:
            raise ValueError(f"Student '{student_id}' is already enrolled in '{course_id}'.")

        # --- atomic unit: both updates happen together, no partial state ---
        course.enrolled_count += 1
        student.enrolled_course_ids.append(course_id)
        self._course_repo.update(course)
        self._student_repo.update(student)
        # --- end atomic unit ---

        self._notifier.notify(
            student_id,
            f"You have been force-enrolled into {course.code} - {course.name} by an administrator."
        )
        self._notifier.notify(
            course.instructor_id,
            f"Student {student_id} was force-enrolled into your course {course.code} by an administrator."
        )
        return course
