"""
service/reporting_service.py

Role: SERVICE TIER — Reporting & Analytics business logic.

ReportingService computes the raw data (lists of dicts / rows) for
each report type. It does NOT format output — that is a Presentation
Tier concern (see presentation/formatters.py). This separation means
the same computed report data could later be rendered as a CLI table,
a JSON API response, or a web page without touching this class
(Open/Closed Principle: new output formats can be added without
modifying this service).

Concrete Report objects themselves are produced via the Factory
Method pattern in patterns/factories.py — this service supplies the
report TYPE and DATA that the factory turns into a polymorphic Report
object.
"""

from data.repositories import CourseRepository, StudentRepository, FacultyRepository


class ReportingService:
    """Business logic for computing enrolment, workload, and popularity reports."""

    def __init__(
        self,
        course_repo: CourseRepository,
        student_repo: StudentRepository,
        faculty_repo: FacultyRepository,
    ):
        self._course_repo = course_repo
        self._student_repo = student_repo
        self._faculty_repo = faculty_repo

    def enrolment_stats_by_department(self) -> list:
        """
        Return one row per department: total courses, total seats,
        total enrolled, average occupancy rate.
        """
        by_dept: dict = {}
        for course in self._course_repo.get_all():
            d = by_dept.setdefault(course.department, {
                "department": course.department,
                "courses": 0,
                "total_capacity": 0,
                "total_enrolled": 0,
            })
            d["courses"] += 1
            d["total_capacity"] += course.capacity
            d["total_enrolled"] += course.enrolled_count

        rows = []
        for d in by_dept.values():
            occupancy = (d["total_enrolled"] / d["total_capacity"] * 100) if d["total_capacity"] else 0.0
            rows.append({
                "Department": d["department"],
                "Courses": d["courses"],
                "Total Capacity": d["total_capacity"],
                "Total Enrolled": d["total_enrolled"],
                "Occupancy %": f"{occupancy:.1f}%",
            })
        return rows

    def faculty_workload_report(self) -> list:
        """Return one row per faculty member: how many courses and total students they handle."""
        faculty_by_id = {f.faculty_id: f for f in self._faculty_repo.get_all()}
        workload: dict = {}
        for course in self._course_repo.get_all():
            w = workload.setdefault(course.instructor_id, {"courses": 0, "students": 0})
            w["courses"] += 1
            w["students"] += course.enrolled_count

        rows = []
        for instructor_id, w in workload.items():
            faculty = faculty_by_id.get(instructor_id)
            name = faculty.name if faculty else instructor_id
            dept = faculty.department if faculty else "Unknown"
            rows.append({
                "Faculty": name,
                "Department": dept,
                "Courses Taught": w["courses"],
                "Total Students": w["students"],
            })
        return rows

    def course_popularity_report(self, capacity_threshold_pct: float = 90.0) -> list:
        """
        Return courses whose occupancy rate is at or above
        `capacity_threshold_pct` (default 90%), sorted most-full first.
        Matches the example use case: "Business school courses
        currently over 90% capacity" (generalised to all departments,
        filterable by department at the presentation layer).
        """
        rows = []
        for course in self._course_repo.get_all():
            occ_pct = course.occupancy_rate() * 100
            if occ_pct >= capacity_threshold_pct:
                rows.append({
                    "Code": course.code,
                    "Name": course.name,
                    "Department": course.department,
                    "Enrolled/Capacity": f"{course.enrolled_count}/{course.capacity}",
                    "Occupancy %": f"{occ_pct:.1f}%",
                })
        rows.sort(key=lambda r: float(r["Occupancy %"].rstrip("%")), reverse=True)
        return rows
