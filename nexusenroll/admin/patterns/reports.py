"""
nexusenroll/admin/patterns/reports.py

Role: PATTERNS — Polymorphic Report product hierarchy, consumed by
the Factory Method in factories.py.

Each Report subclass wraps a report title and its computed row data
(dicts) from ReportingService, and exposes a uniform to_rows()
interface. Because all reports share this interface, the Presentation
Tier's table formatter (presentation/formatters.py) can render ANY
report type without an if/elif chain checking the report's class —
and adding a brand new report type later only means adding a new
Report subclass + a new ReportingService method, never touching the
formatter or the Facade (Open/Closed Principle).
"""

from abc import ABC, abstractmethod


class Report(ABC):
    """Abstract base for all report types (the Factory Method's 'Product')."""

    def __init__(self, title: str, rows: list):
        self.title = title
        self.rows = rows

    @abstractmethod
    def report_type(self) -> str:
        """Short machine-readable identifier for this report type."""
        ...

    def to_rows(self) -> list:
        """Return the report's data as a list of dict rows (column -> value)."""
        return self.rows


class EnrolmentStatsReport(Report):
    """Enrolment statistics grouped by department."""

    def report_type(self) -> str:
        return "enrolment_stats_by_department"


class FacultyWorkloadReport(Report):
    """Faculty workload: courses taught and total students per faculty member."""

    def report_type(self) -> str:
        return "faculty_workload"


class CoursePopularityReport(Report):
    """Courses at or above a capacity threshold, most-full first."""

    def report_type(self) -> str:
        return "course_popularity"
