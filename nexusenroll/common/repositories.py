"""
nexusenroll/common/repositories.py

Role: SHARED DATA TIER — Repository interfaces + CSV-backed
implementations.

Every repository below is split into:
  1. An abstract base class (the "port") declaring WHAT operations
     exist, with no storage detail.
  2. A CSV-backed concrete implementation (the "adapter") that
     satisfies that contract by keeping an in-memory dict as a working
     copy and reading/writing one CSV file under data/ as the actual
     store.

This is the Dependency Inversion Principle: every Service Tier class
in all three modules (StudentService, FacultyServiceImpl,
CourseService/AccountService/OverrideService/ReportingService in the
Administrator module) is written against CourseRepository /
StudentRepository / FacultyRepository / ProgramRepository (the
abstract classes), never against the CSV-backed classes directly.
Swapping in a real database later means writing e.g.
PostgresCourseRepository(CourseRepository) and changing one line of
wiring in nexusenroll/system/app.py — no service code in any of the
three modules changes.

Persistence model: load() reads the whole CSV into memory once, at
construction. save() rewrites the whole CSV from the current in-memory
state. Individual mutations (add/update/delete/set_status) only touch
the in-memory dict — they do NOT save on every call, because several
mutations happen as a related group (e.g. an enrolment updates both a
Course and a Student) and writing the file after every single list
append would mean needless disk I/O with no correctness benefit. The
composition root (nexusenroll/system/app.py) calls save() on every
repository at the end of each top-level menu action, which is both
simpler and safer than tracking every mutation call site by hand — see
that file for where the commit points are.

Single-source-of-truth note: nexusenroll/system/app.py (the
composition root) constructs exactly ONE instance of each repository
and hands the SAME instance to the Student service, the Faculty
service, and the Administrator facade. That is the mechanism by which
the three independently-developed modules become one consistent
system rather than three programs with three disagreeing copies of
the data.
"""

from abc import ABC, abstractmethod
from typing import Optional

from nexusenroll.common.domain import Course, Program, Student, Faculty, Schedule, AccountStatus, AuditLogEntry
from nexusenroll.common import csv_utils as csv_


# --------------------------------------------------------------------------
# Course Repository
# --------------------------------------------------------------------------

class CourseRepository(ABC):
    """Abstract data-access contract for Course entities (DATA TIER port)."""

    @abstractmethod
    def get_all(self) -> list: ...

    @abstractmethod
    def get_by_id(self, course_id: str) -> Optional[Course]: ...

    @abstractmethod
    def add(self, course: Course) -> None: ...

    @abstractmethod
    def update(self, course: Course) -> None: ...

    @abstractmethod
    def delete(self, course_id: str) -> bool: ...

    @abstractmethod
    def save(self) -> None: ...


class CSVCourseRepository(CourseRepository):
    """CSV-backed adapter for CourseRepository. Persists to data/courses.csv."""

    FIELDNAMES = [
        "course_id", "code", "name", "description", "department", "instructor_id",
        "capacity", "days", "start_time", "end_time", "location",
        "prerequisites", "enrolled_student_ids", "waitlisted_student_ids", "semester",
    ]

    def __init__(self, csv_path: str):
        self._path = csv_path
        self._courses: dict = {}
        self._load()

    def _load(self) -> None:
        for row in csv_.read_rows(self._path):
            course = Course(
                course_id=row["course_id"], code=row["code"], name=row["name"],
                description=row["description"], department=row["department"],
                instructor_id=row["instructor_id"], capacity=int(row["capacity"]),
                schedule=Schedule(
                    days=csv_.decode_list(row["days"]),
                    start_time=row["start_time"], end_time=row["end_time"], location=row["location"],
                ),
                prerequisites=csv_.decode_list(row["prerequisites"]),
                enrolled_student_ids=csv_.decode_list(row["enrolled_student_ids"]),
                waitlisted_student_ids=csv_.decode_list(row["waitlisted_student_ids"]),
                semester=row.get("semester") or "2026-S2",
            )
            self._courses[course.course_id] = course

    def save(self) -> None:
        rows = [self._to_row(c) for c in self._courses.values()]
        csv_.write_rows(self._path, self.FIELDNAMES, rows)

    def _to_row(self, c: Course) -> dict:
        return {
            "course_id": c.course_id, "code": c.code, "name": c.name,
            "description": c.description, "department": c.department,
            "instructor_id": c.instructor_id, "capacity": c.capacity,
            "days": csv_.encode_list(c.schedule.days), "start_time": c.schedule.start_time,
            "end_time": c.schedule.end_time, "location": c.schedule.location,
            "prerequisites": csv_.encode_list(c.prerequisites),
            "enrolled_student_ids": csv_.encode_list(c.enrolled_student_ids),
            "waitlisted_student_ids": csv_.encode_list(c.waitlisted_student_ids),
            "semester": c.semester,
        }

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
    def get_all(self) -> list: ...

    @abstractmethod
    def get_by_id(self, program_id: str) -> Optional[Program]: ...

    @abstractmethod
    def add(self, program: Program) -> None: ...

    @abstractmethod
    def update(self, program: Program) -> None: ...

    @abstractmethod
    def save(self) -> None: ...


class CSVProgramRepository(ProgramRepository):
    """CSV-backed adapter for ProgramRepository. Persists to data/programs.csv."""

    FIELDNAMES = ["program_id", "name", "required_courses", "total_credits"]

    def __init__(self, csv_path: str):
        self._path = csv_path
        self._programs: dict = {}
        self._load()

    def _load(self) -> None:
        for row in csv_.read_rows(self._path):
            program = Program(
                program_id=row["program_id"], name=row["name"],
                required_courses=csv_.decode_list(row["required_courses"]),
                total_credits=int(row["total_credits"]) if row["total_credits"] else 0,
            )
            self._programs[program.program_id] = program

    def save(self) -> None:
        rows = [
            {
                "program_id": p.program_id, "name": p.name,
                "required_courses": csv_.encode_list(p.required_courses),
                "total_credits": p.total_credits,
            }
            for p in self._programs.values()
        ]
        csv_.write_rows(self._path, self.FIELDNAMES, rows)

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
    def get_all(self) -> list: ...

    @abstractmethod
    def get_by_id(self, student_id: str) -> Optional[Student]: ...

    @abstractmethod
    def add(self, student: Student) -> None: ...

    @abstractmethod
    def update(self, student: Student) -> None: ...

    @abstractmethod
    def set_status(self, student_id: str, status: AccountStatus) -> bool: ...

    @abstractmethod
    def save(self) -> None: ...


class CSVStudentRepository(StudentRepository):
    """CSV-backed adapter for StudentRepository. Persists to data/students.csv."""

    FIELDNAMES = [
        "student_id", "name", "email", "advisor", "program_id", "status",
        "completed_courses", "enrolled_course_ids", "waitlisted_course_ids",
    ]

    def __init__(self, csv_path: str):
        self._path = csv_path
        self._students: dict = {}
        self._load()

    def _load(self) -> None:
        for row in csv_.read_rows(self._path):
            student = Student(
                student_id=row["student_id"], name=row["name"], email=row["email"],
                advisor=row.get("advisor") or None,
                program_id=row.get("program_id") or None,
                status=AccountStatus(row["status"]) if row.get("status") else AccountStatus.ACTIVE,
                completed_courses=csv_.decode_dict(row["completed_courses"]),
                enrolled_course_ids=csv_.decode_list(row["enrolled_course_ids"]),
                waitlisted_course_ids=csv_.decode_list(row["waitlisted_course_ids"]),
            )
            self._students[student.student_id] = student

    def save(self) -> None:
        rows = [
            {
                "student_id": s.student_id, "name": s.name, "email": s.email,
                "advisor": s.advisor or "", "program_id": s.program_id or "",
                "status": s.status.value,
                "completed_courses": csv_.encode_dict(s.completed_courses),
                "enrolled_course_ids": csv_.encode_list(s.enrolled_course_ids),
                "waitlisted_course_ids": csv_.encode_list(s.waitlisted_course_ids),
            }
            for s in self._students.values()
        ]
        csv_.write_rows(self._path, self.FIELDNAMES, rows)

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
    def get_all(self) -> list: ...

    @abstractmethod
    def get_by_id(self, faculty_id: str) -> Optional[Faculty]: ...

    @abstractmethod
    def add(self, faculty: Faculty) -> None: ...

    @abstractmethod
    def update(self, faculty: Faculty) -> None: ...

    @abstractmethod
    def set_status(self, faculty_id: str, status: AccountStatus) -> bool: ...

    @abstractmethod
    def save(self) -> None: ...


class CSVFacultyRepository(FacultyRepository):
    """CSV-backed adapter for FacultyRepository. Persists to data/faculty.csv."""

    FIELDNAMES = ["faculty_id", "name", "email", "department", "status"]

    def __init__(self, csv_path: str):
        self._path = csv_path
        self._faculty: dict = {}
        self._load()

    def _load(self) -> None:
        for row in csv_.read_rows(self._path):
            faculty = Faculty(
                faculty_id=row["faculty_id"], name=row["name"], email=row["email"],
                department=row["department"],
                status=AccountStatus(row["status"]) if row.get("status") else AccountStatus.ACTIVE,
            )
            self._faculty[faculty.faculty_id] = faculty

    def save(self) -> None:
        rows = [
            {
                "faculty_id": f.faculty_id, "name": f.name, "email": f.email,
                "department": f.department, "status": f.status.value,
            }
            for f in self._faculty.values()
        ]
        csv_.write_rows(self._path, self.FIELDNAMES, rows)

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
    def add(self, entry: AuditLogEntry) -> None: ...

    @abstractmethod
    def get_all(self) -> list: ...

    @abstractmethod
    def save(self) -> None: ...


class CSVAuditLogRepository(AuditLogRepository):
    """
    CSV-backed adapter for AuditLogRepository. Persists to
    data/audit_log.csv. Append-only, so save() rewrites the file from
    the full in-memory list — same commit-point model as the other
    repositories, kept consistent rather than special-cased as a
    true streaming append, since the composition root already saves
    every repository together at each commit point.
    """

    FIELDNAMES = ["command_name", "actor", "details", "success", "timestamp"]

    def __init__(self, csv_path: str):
        self._path = csv_path
        self._entries: list = []
        self._load()

    def _load(self) -> None:
        for row in csv_.read_rows(self._path):
            self._entries.append(AuditLogEntry(
                command_name=row["command_name"], actor=row["actor"],
                details=row["details"], success=row["success"] == "True",
                timestamp=row["timestamp"],
            ))

    def save(self) -> None:
        rows = [
            {
                "command_name": e.command_name, "actor": e.actor,
                "details": e.details, "success": e.success, "timestamp": e.timestamp,
            }
            for e in self._entries
        ]
        csv_.write_rows(self._path, self.FIELDNAMES, rows)

    def add(self, entry: AuditLogEntry) -> None:
        self._entries.append(entry)

    def get_all(self) -> list:
        return list(self._entries)
