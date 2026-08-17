"""
data/entities.py

Role: DATA TIER — Entity (domain model) definitions.

These are plain data-holding classes (similar to DTOs / domain
entities). They have no knowledge of how they are stored (that is
the Repository's job) and no business validation logic (that is the
Service Tier's job) — this keeps each class focused on a single
responsibility (SOLID: Single Responsibility Principle).

Shared-system note: the fields on Course (capacity/enrolled_count)
and on Student (completed_courses, grades) are deliberately shaped
to match what the Student Module (capacity/prerequisite checks) and
Faculty Module (roster/grade data) would also need to read, so this
Admin Module's data shapes stay consistent with the rest of
NexusEnroll if/when a shared database replaces these mock structures.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class AccountStatus(Enum):
    """Lifecycle status shared by Student and Faculty accounts."""
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"


class GradeStatus(Enum):
    """
    Status of a submitted grade record.

    Mirrors the Faculty Module's grade-submission workflow
    (Pending -> Submitted) described in the requirements, so admin
    reporting on grades stays consistent with what Faculty produces.
    """
    PENDING = "PENDING"
    SUBMITTED = "SUBMITTED"


@dataclass
class Course:
    """
    A single course offering (one section, one semester).

    capacity / enrolled_count are the exact numbers the Student
    Module's capacity-check would read before allowing an add, so
    the Admin Module must keep them consistent when it force-enrols
    or edits a course.
    """
    course_id: str
    code: str                      # e.g. "CS201"
    name: str
    description: str
    department: str
    instructor_id: str
    capacity: int
    enrolled_count: int
    schedule: str                  # e.g. "Mon/Wed 10:00-11:30, Room A2"
    prerequisites: list = field(default_factory=list)  # list[str] course codes
    semester: str = "2026-S2"

    def occupancy_rate(self) -> float:
        """Return seats-filled ratio (0.0 - 1.0+), used by popularity reports."""
        if self.capacity == 0:
            return 0.0
        return self.enrolled_count / self.capacity

    def is_full(self) -> bool:
        """True if no seats remain (used by override/force-add workflow)."""
        return self.enrolled_count >= self.capacity


@dataclass
class Program:
    """A degree program: a named set of required courses and total credits."""
    program_id: str
    name: str
    required_courses: list = field(default_factory=list)  # list[str] course codes
    total_credits: int = 0


@dataclass
class Student:
    """
    A student account.

    completed_courses / grades mirror what the Student Module's
    'Academic Progress Tracking' feature and the Faculty Module's
    grade submissions would populate — the Admin Module only edits
    account-level fields (status, program) here, not grades directly.
    """
    student_id: str
    name: str
    email: str
    program_id: Optional[str] = None
    status: AccountStatus = AccountStatus.ACTIVE
    completed_courses: list = field(default_factory=list)   # list[str] course codes
    enrolled_course_ids: list = field(default_factory=list)  # current semester


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
    A single record of an executed admin Command.

    This is the 'action/audit log' the requirements ask the Command
    pattern to enable: every concrete Command appends one of these
    after it runs (see patterns/commands.py).
    """
    command_name: str
    actor: str            # which admin performed it
    details: str
    success: bool
    timestamp: str
