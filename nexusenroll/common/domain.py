"""
nexusenroll/common/domain.py

Role: SHARED DATA TIER — canonical entity (domain model) definitions.

These are plain data-holding classes (DTO-style domain entities). They
carry no storage logic (that is the Repository's job, see
repositories.py) and no cross-cutting business validation (that is
each service's job) — this keeps every class focused on exactly one
responsibility (SOLID: Single Responsibility Principle).

Every one of the three modules (student, faculty, admin) imports
Course / Student / Faculty / Program / Schedule / AccountStatus from
HERE rather than declaring their own copies. That is what makes this
one integrated system instead of three programs that happen to share a
repository: when the Administrator force-enrols a student, the Student
module's own capacity check sees the update immediately, because both
are reading the same Course object out of the same CSV-backed
repository (see repositories.py).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional


class AccountStatus(Enum):
    """Lifecycle status shared by Student and Faculty accounts."""
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"


@dataclass
class Schedule:
    """
    A weekly meeting pattern for a course section.

    overlaps() is what the Student module's TimeConflictValidator
    (Chain of Responsibility) calls to decide whether two courses
    clash; it is kept on Schedule itself (rather than duplicated
    inside the validator) because "do two schedules overlap" is a
    property of the Schedule value object, not of the validation
    workflow that happens to use it (Single Responsibility / high
    cohesion).
    """
    days: List[str] = field(default_factory=list)          # e.g. ["Mon", "Wed"]
    start_time: str = ""                                     # 24hr "HH:MM"
    end_time: str = ""
    location: str = "TBA"

    @classmethod
    def freetext(cls, text: str) -> "Schedule":
        """
        Build a Schedule from a single free-text string (used by the
        Administrator CLI, which accepts one line of text like
        "Mon/Wed 10:00-11:30, Room A2" rather than four separate
        fields). Since the days/times can't be reliably parsed back
        out of arbitrary free text, `days` is left empty — which
        makes overlaps() always return False for it, i.e. a
        manually/administratively entered schedule never triggers a
        false-positive time-conflict against a student's other
        courses. This is a deliberate, documented trade-off, not an
        oversight.
        """
        return cls(days=[], start_time="", end_time="", location=text or "TBA")

    def overlaps(self, other: "Schedule") -> bool:
        """Two schedules overlap if they share a day AND their time ranges intersect."""
        if not self.days or not other.days:
            return False
        if not set(self.days) & set(other.days):
            return False
        return not (self.end_time <= other.start_time or other.end_time <= self.start_time)

    def __str__(self) -> str:
        if not self.days:
            return self.location
        return f"{'/'.join(self.days)} {self.start_time}-{self.end_time} @ {self.location}"


@dataclass
class Course:
    """
    A single course offering (one section, one semester).

    enrolled_student_ids / waitlisted_student_ids are the single
    source of truth for "who is in this class" — the Student module's
    capacity check, the Faculty module's class roster, and the
    Administrator's enrolment/popularity reports all read the SAME two
    lists, instead of each module keeping (and risking disagreement
    about) its own headcount. CSVCourseRepository persists exactly
    these fields to data/courses.csv.
    """
    course_id: str                 # canonical id, e.g. "CS201" (== code)
    code: str
    name: str
    description: str
    department: str
    instructor_id: str
    capacity: int
    schedule: Schedule
    prerequisites: List[str] = field(default_factory=list)
    enrolled_student_ids: List[str] = field(default_factory=list)
    waitlisted_student_ids: List[str] = field(default_factory=list)
    semester: str = "2026-S2"

    @property
    def enrolled_count(self) -> int:
        return len(self.enrolled_student_ids)

    @property
    def available_seats(self) -> int:
        return self.capacity - self.enrolled_count

    def is_full(self) -> bool:
        return self.available_seats <= 0

    def occupancy_rate(self) -> float:
        """Seats-filled ratio (0.0 - 1.0+), used by the popularity report."""
        if self.capacity == 0:
            return 0.0
        return self.enrolled_count / self.capacity

    def roster(self) -> List[str]:
        return list(self.enrolled_student_ids)


@dataclass
class Program:
    """A degree program: a named set of required courses and total credits."""
    program_id: str
    name: str
    required_courses: List[str] = field(default_factory=list)
    total_credits: int = 0


@dataclass
class Student:
    """
    A student account.

    completed_courses maps course_id -> final grade, populated by the
    Faculty module's grade-submission workflow (via the
    "grade_approved" ESB event, see nexusenroll/system/bus_hub.py) —
    the Student module's own Academic Progress Tracking feature reads
    this same dict, so a grade posted by faculty is immediately
    reflected in the student's progress report, and is written back to
    data/students.csv the next time the repository is saved.
    """
    student_id: str
    name: str
    email: str
    advisor: Optional[str] = None
    program_id: Optional[str] = None
    status: AccountStatus = AccountStatus.ACTIVE
    completed_courses: Dict[str, str] = field(default_factory=dict)
    enrolled_course_ids: List[str] = field(default_factory=list)
    waitlisted_course_ids: List[str] = field(default_factory=list)


@dataclass
class Faculty:
    """A faculty account."""
    faculty_id: str
    name: str
    email: str
    department: str
    status: AccountStatus = AccountStatus.ACTIVE


@dataclass
class AuditLogEntry:
    """
    A single record of an executed Administrator Command.

    This is the audit log the assignment's Command pattern usage is
    meant to enable: every concrete AdminCommand appends one of these
    after it runs (see nexusenroll/admin/patterns/commands.py). It is
    persisted, append-only, to data/audit_log.csv.
    """
    command_name: str
    actor: str
    details: str
    success: bool
    timestamp: str
