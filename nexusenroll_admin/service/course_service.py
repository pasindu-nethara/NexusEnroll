"""
service/course_service.py

Role: SERVICE TIER — Course & Program management business logic.

CourseService and ProgramService each have a single responsibility
(SOLID: SRP) — course CRUD vs. program CRUD — even though they are
closely related, so a change to how programs are validated never
risks breaking course logic and vice versa.

Both depend only on repository abstractions (data/repositories.py),
not concrete in-memory classes — Dependency Inversion Principle.
"""

from typing import Optional

from data.entities import Course, Program
from data.repositories import CourseRepository, ProgramRepository


class CourseService:
    """Business logic for creating, editing, and deleting courses."""

    def __init__(self, course_repo: CourseRepository):
        self._course_repo = course_repo

    def list_courses(self) -> list:
        """Return all courses (used by CLI listing and reports)."""
        return self._course_repo.get_all()

    def get_course(self, course_id: str) -> Optional[Course]:
        return self._course_repo.get_by_id(course_id)

    def create_course(self, course: Course) -> None:
        """
        Persist a new course.

        Validation: course_id must be unique and capacity must be
        non-negative. The Course object itself is expected to have
        been built via CourseFactory (patterns/factories.py) — this
        method focuses only on the business rule of "is this a valid
        course to add", not on how the object gets constructed.
        """
        if self._course_repo.get_by_id(course.course_id) is not None:
            raise ValueError(f"Course ID '{course.course_id}' already exists.")
        if course.capacity < 0:
            raise ValueError("Capacity cannot be negative.")
        if course.enrolled_count < 0:
            raise ValueError("Enrolled count cannot be negative.")
        self._course_repo.add(course)

    def edit_course(self, course_id: str, **updates) -> Course:
        """
        Edit fields on an existing course in place. `updates` may
        include any of: name, description, department, instructor_id,
        capacity, schedule, prerequisites.
        """
        course = self._course_repo.get_by_id(course_id)
        if course is None:
            raise ValueError(f"Course '{course_id}' not found.")

        if "capacity" in updates:
            new_cap = updates["capacity"]
            if new_cap < course.enrolled_count:
                raise ValueError(
                    f"Cannot set capacity ({new_cap}) below current enrolled "
                    f"count ({course.enrolled_count})."
                )
            course.capacity = new_cap
        for field_name in ("name", "description", "department", "instructor_id", "schedule"):
            if field_name in updates:
                setattr(course, field_name, updates[field_name])
        if "prerequisites" in updates:
            course.prerequisites = updates["prerequisites"]

        self._course_repo.update(course)
        return course

    def delete_course(self, course_id: str) -> Course:
        """
        Delete a course. Returns the deleted Course so the caller
        (e.g. DeleteCourseCommand) can decide whether to notify
        enrolled students via the NotificationService extension point.
        """
        course = self._course_repo.get_by_id(course_id)
        if course is None:
            raise ValueError(f"Course '{course_id}' not found.")
        self._course_repo.delete(course_id)
        return course


class ProgramService:
    """Business logic for creating and editing degree programs."""

    def __init__(self, program_repo: ProgramRepository):
        self._program_repo = program_repo

    def list_programs(self) -> list:
        return self._program_repo.get_all()

    def get_program(self, program_id: str) -> Optional[Program]:
        return self._program_repo.get_by_id(program_id)

    def create_program(self, program: Program) -> None:
        """Persist a new degree program. program_id must be unique."""
        if self._program_repo.get_by_id(program.program_id) is not None:
            raise ValueError(f"Program ID '{program.program_id}' already exists.")
        if program.total_credits < 0:
            raise ValueError("Total credits cannot be negative.")
        self._program_repo.add(program)

    def edit_program(self, program_id: str, **updates) -> Program:
        """Edit fields on an existing program: name, required_courses, total_credits."""
        program = self._program_repo.get_by_id(program_id)
        if program is None:
            raise ValueError(f"Program '{program_id}' not found.")
        if "name" in updates:
            program.name = updates["name"]
        if "required_courses" in updates:
            program.required_courses = updates["required_courses"]
        if "total_credits" in updates:
            if updates["total_credits"] < 0:
                raise ValueError("Total credits cannot be negative.")
            program.total_credits = updates["total_credits"]
        self._program_repo.update(program)
        return program
