"""
patterns/factories.py

Role: PATTERNS — Factory Method (creational design pattern).

Three independent Factory Method hierarchies are demonstrated here,
matching the assignment's example objects: Reports, Accounts, and
Course/Program entities.

The Factory Method pattern lets a creator class define a
create_*() method whose concrete return type is decided by a
subclass, so calling code depends only on the abstract creator/
product, never on concrete classes directly. This satisfies
Open/Closed: adding a new report type, account type, or entity type
means adding a new small factory subclass — no existing factory code
is modified.
"""

from abc import ABC, abstractmethod

from data.entities import Course, Program, Student, Faculty, AccountStatus
from patterns.reports import (
    Report,
    EnrolmentStatsReport,
    FacultyWorkloadReport,
    CoursePopularityReport,
)


# ============================================================
# Factory Method #1 — Report creation
# ============================================================

class ReportFactory(ABC):
    """Abstract creator: declares the Factory Method create_report()."""

    @abstractmethod
    def create_report(self, title: str, rows: list) -> Report:
        ...


class EnrolmentStatsReportFactory(ReportFactory):
    """Concrete creator producing EnrolmentStatsReport instances."""

    def create_report(self, title: str, rows: list) -> Report:
        return EnrolmentStatsReport(title, rows)


class FacultyWorkloadReportFactory(ReportFactory):
    """Concrete creator producing FacultyWorkloadReport instances."""

    def create_report(self, title: str, rows: list) -> Report:
        return FacultyWorkloadReport(title, rows)


class CoursePopularityReportFactory(ReportFactory):
    """Concrete creator producing CoursePopularityReport instances."""

    def create_report(self, title: str, rows: list) -> Report:
        return CoursePopularityReport(title, rows)


# ============================================================
# Factory Method #2 — Account creation (Student / Faculty)
# ============================================================

class AccountFactory(ABC):
    """Abstract creator: declares the Factory Method create_account()."""

    @abstractmethod
    def create_account(self, **kwargs):
        ...


class StudentAccountFactory(AccountFactory):
    """Concrete creator producing Student entities with sane defaults."""

    def create_account(self, **kwargs) -> Student:
        return Student(
            student_id=kwargs["account_id"],
            name=kwargs["name"],
            email=kwargs["email"],
            program_id=kwargs.get("program_id"),
            status=AccountStatus.ACTIVE,
            completed_courses=[],
            enrolled_course_ids=[],
        )


class FacultyAccountFactory(AccountFactory):
    """Concrete creator producing Faculty entities with sane defaults."""

    def create_account(self, **kwargs) -> Faculty:
        return Faculty(
            faculty_id=kwargs["account_id"],
            name=kwargs["name"],
            email=kwargs["email"],
            department=kwargs.get("department", "Unassigned"),
            status=AccountStatus.ACTIVE,
        )


# ============================================================
# Factory Method #3 — Course / Program entity creation
# ============================================================

class EntityFactory(ABC):
    """Abstract creator: declares the Factory Method create_entity()."""

    @abstractmethod
    def create_entity(self, **kwargs):
        ...


class CourseFactory(EntityFactory):
    """Concrete creator producing Course entities with sane defaults (0 enrolled)."""

    def create_entity(self, **kwargs) -> Course:
        return Course(
            course_id=kwargs["course_id"],
            code=kwargs["code"],
            name=kwargs["name"],
            description=kwargs.get("description", ""),
            department=kwargs["department"],
            instructor_id=kwargs["instructor_id"],
            capacity=kwargs["capacity"],
            enrolled_count=0,
            schedule=kwargs.get("schedule", "TBA"),
            prerequisites=kwargs.get("prerequisites", []),
            semester=kwargs.get("semester", "2026-S2"),
        )


class ProgramFactory(EntityFactory):
    """Concrete creator producing Program entities."""

    def create_entity(self, **kwargs) -> Program:
        return Program(
            program_id=kwargs["program_id"],
            name=kwargs["name"],
            required_courses=kwargs.get("required_courses", []),
            total_credits=kwargs.get("total_credits", 0),
        )
