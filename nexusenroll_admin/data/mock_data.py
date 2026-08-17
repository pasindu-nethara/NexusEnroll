"""
data/mock_data.py

Role: DATA TIER — Mock data seeding.

Populates the in-memory repositories with a small, realistic dataset
so the CLI is immediately demoable (per the assignment's requirement
for "realistic in-memory mock data ... so the CLI runs and demos
immediately"). This is intentionally the ONLY place that constructs
sample entities directly with dataclass constructors — everywhere
else in the Service/Presentation tiers, new entities are created via
the Factory Method pattern (see patterns/factories.py), since this
is just bootstrapping fixture data, not a user-facing creation flow.
"""

from data.entities import Course, Program, Student, Faculty, AccountStatus
from data.repositories import (
    CourseRepository,
    ProgramRepository,
    StudentRepository,
    FacultyRepository,
)


def seed_mock_data(
    course_repo: CourseRepository,
    program_repo: ProgramRepository,
    student_repo: StudentRepository,
    faculty_repo: FacultyRepository,
) -> None:
    """Insert a small set of sample courses, programs, students, and faculty."""

    # --- Faculty -----------------------------------------------------
    faculty_repo.add(Faculty("F001", "Dr. Nadia Perera", "nadia.perera@nexusuni.edu", "Computer Science"))
    faculty_repo.add(Faculty("F002", "Dr. Ruwan Silva", "ruwan.silva@nexusuni.edu", "Business"))

    # --- Courses -------------------------------------------------------
    course_repo.add(Course(
        course_id="C001", code="CS201", name="Data Structures & Algorithms",
        description="Core data structures, algorithm design and analysis.",
        department="Computer Science", instructor_id="F001",
        capacity=30, enrolled_count=28,
        schedule="Mon/Wed 10:00-11:30, Room A2",
        prerequisites=["CS101"],
    ))
    course_repo.add(Course(
        course_id="C002", code="CS301", name="Software Architecture",
        description="Architectural styles, SOA, design patterns.",
        department="Computer Science", instructor_id="F001",
        capacity=25, enrolled_count=25,
        schedule="Tue/Thu 13:00-14:30, Room B1",
        prerequisites=["CS201"],
    ))
    course_repo.add(Course(
        course_id="C003", code="BUS210", name="Principles of Marketing",
        description="Foundations of marketing strategy and consumer behaviour.",
        department="Business", instructor_id="F002",
        capacity=40, enrolled_count=39,
        schedule="Mon/Wed 09:00-10:30, Room C3",
        prerequisites=[],
    ))

    # --- Programs --------------------------------------------------------
    program_repo.add(Program(
        program_id="P001", name="BSc Computer Science",
        required_courses=["CS101", "CS201", "CS301"], total_credits=120,
    ))
    program_repo.add(Program(
        program_id="P002", name="BSc Business Administration",
        required_courses=["BUS101", "BUS210"], total_credits=108,
    ))

    # --- Students ----------------------------------------------------------
    student_repo.add(Student(
        student_id="S001", name="Kasun Fernando", email="kasun.f@nexusuni.edu",
        program_id="P001", status=AccountStatus.ACTIVE,
        completed_courses=["CS101"], enrolled_course_ids=["C001"],
    ))
    student_repo.add(Student(
        student_id="S002", name="Amaya Jayasuriya", email="amaya.j@nexusuni.edu",
        program_id="P001", status=AccountStatus.ACTIVE,
        completed_courses=["CS101", "CS201"], enrolled_course_ids=["C002"],
    ))
    student_repo.add(Student(
        student_id="S003", name="Tharindu Bandara", email="tharindu.b@nexusuni.edu",
        program_id="P002", status=AccountStatus.ACTIVE,
        completed_courses=[], enrolled_course_ids=["C003"],
    ))
