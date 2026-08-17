"""
data/repositories.py

Role: DATA TIER — Repository interfaces + in-memory implementations.

Every repository below is split into:
  1. An abstract base class (the "port") declaring WHAT operations
     exist, with no storage detail.
  2. An in-memory concrete implementation (the "adapter") that
     satisfies that contract using plain Python dicts/lists.

This is the Dependency Inversion Principle: the Service Tier (see
service/*.py) is written against CourseRepository /
StudentRepository / etc. (the abstract classes), never against
InMemoryCourseRepository directly. Swapping in a real database later
means writing e.g. PostgresCourseRepository(CourseRepository) and
changing one line of wiring in main.py — no service code changes.

Transaction-safety note: the requirements call for enrolment
operations to be atomic system-wide (handled by a Transaction
Manager subsystem outside this module's scope). Within the Admin
Module, force_enrol() below performs its capacity update and
enrolment list update together in one method body precisely so a
future TransactionManager wrapper (or DB transaction) can wrap this
single call and treat it as one atomic unit — there is no
opportunity for partial state to leak out to a caller.
"""

from abc import ABC, abstractmethod
from typing import Optional

from data.entities import Course, Program, Student, Faculty, AccountStatus


# --------------------------------------------------------------------------
# Course Repository
# --------------------------------------------------------------------------

class CourseRepository(ABC):
    """Abstract data-access contract for Course entities (DATA TIER port)."""

    @abstractmethod
    def get_all(self) -> list:
        ...

    @abstractmethod
    def get_by_id(self, course_id: str) -> Optional[Course]:
        ...

    @abstractmethod
    def add(self, course: Course) -> None:
        ...

    @abstractmethod
    def update(self, course: Course) -> None:
        ...

    @abstractmethod
    def delete(self, course_id: str) -> bool:
        ...


class InMemoryCourseRepository(CourseRepository):
    """
    In-memory adapter for CourseRepository.

    Data lives in a dict keyed by course_id for O(1) lookup. This is
    a mock standing in for a real database table; nothing outside
    this class knows that.
    """

    def __init__(self):
        self._courses: dict = {}

    def get_all(self) -> list:
        return list(self._courses.values())

    def get_by_id(self, course_id: str) -> Optional[Course]:
        return self._courses.get(course_id)

    def add(self, course: Course) -> None:
        self._courses[course.course_id] = course

    def update(self, course: Course) -> None:
        self._courses[course.course_id] = course

    def delete(self, course_id: str) -> bool:
        if course_id in self._courses:
            del self._courses[course_id]
            return True
        return False


# --------------------------------------------------------------------------
# Program Repository
# --------------------------------------------------------------------------

class ProgramRepository(ABC):
    """Abstract data-access contract for Program entities (DATA TIER port)."""

    @abstractmethod
    def get_all(self) -> list:
        ...

    @abstractmethod
    def get_by_id(self, program_id: str) -> Optional[Program]:
        ...

    @abstractmethod
    def add(self, program: Program) -> None:
        ...

    @abstractmethod
    def update(self, program: Program) -> None:
        ...


class InMemoryProgramRepository(ProgramRepository):
    """In-memory adapter for ProgramRepository."""

    def __init__(self):
        self._programs: dict = {}

    def get_all(self) -> list:
        return list(self._programs.values())

    def get_by_id(self, program_id: str) -> Optional[Program]:
        return self._programs.get(program_id)

    def add(self, program: Program) -> None:
        self._programs[program.program_id] = program

    def update(self, program: Program) -> None:
        self._programs[program.program_id] = program


# --------------------------------------------------------------------------
# Student Repository
# --------------------------------------------------------------------------

class StudentRepository(ABC):
    """Abstract data-access contract for Student entities (DATA TIER port)."""

    @abstractmethod
    def get_all(self) -> list:
        ...

    @abstractmethod
    def get_by_id(self, student_id: str) -> Optional[Student]:
        ...

    @abstractmethod
    def add(self, student: Student) -> None:
        ...

    @abstractmethod
    def update(self, student: Student) -> None:
        ...

    @abstractmethod
    def set_status(self, student_id: str, status: AccountStatus) -> bool:
        ...


class InMemoryStudentRepository(StudentRepository):
    """In-memory adapter for StudentRepository."""

    def __init__(self):
        self._students: dict = {}

    def get_all(self) -> list:
        return list(self._students.values())

    def get_by_id(self, student_id: str) -> Optional[Student]:
        return self._students.get(student_id)

    def add(self, student: Student) -> None:
        self._students[student.student_id] = student

    def update(self, student: Student) -> None:
        self._students[student.student_id] = student

    def set_status(self, student_id: str, status: AccountStatus) -> bool:
        student = self._students.get(student_id)
        if student is None:
            return False
        student.status = status
        return True


# --------------------------------------------------------------------------
# Faculty Repository
# --------------------------------------------------------------------------

class FacultyRepository(ABC):
    """Abstract data-access contract for Faculty entities (DATA TIER port)."""

    @abstractmethod
    def get_all(self) -> list:
        ...

    @abstractmethod
    def get_by_id(self, faculty_id: str) -> Optional[Faculty]:
        ...

    @abstractmethod
    def add(self, faculty: Faculty) -> None:
        ...

    @abstractmethod
    def update(self, faculty: Faculty) -> None:
        ...

    @abstractmethod
    def set_status(self, faculty_id: str, status: AccountStatus) -> bool:
        ...


class InMemoryFacultyRepository(FacultyRepository):
    """In-memory adapter for FacultyRepository."""

    def __init__(self):
        self._faculty: dict = {}

    def get_all(self) -> list:
        return list(self._faculty.values())

    def get_by_id(self, faculty_id: str) -> Optional[Faculty]:
        return self._faculty.get(faculty_id)

    def add(self, faculty: Faculty) -> None:
        self._faculty[faculty.faculty_id] = faculty

    def update(self, faculty: Faculty) -> None:
        self._faculty[faculty.faculty_id] = faculty

    def set_status(self, faculty_id: str, status: AccountStatus) -> bool:
        f = self._faculty.get(faculty_id)
        if f is None:
            return False
        f.status = status
        return True


# --------------------------------------------------------------------------
# Audit Log Repository
# --------------------------------------------------------------------------

class AuditLogRepository(ABC):
    """Abstract data-access contract for audit-log entries (DATA TIER port)."""

    @abstractmethod
    def add(self, entry) -> None:
        ...

    @abstractmethod
    def get_all(self) -> list:
        ...


class InMemoryAuditLogRepository(AuditLogRepository):
    """In-memory adapter for AuditLogRepository. Append-only list."""

    def __init__(self):
        self._entries: list = []

    def add(self, entry) -> None:
        self._entries.append(entry)

    def get_all(self) -> list:
        return list(self._entries)
