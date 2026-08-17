"""
NexusEnroll - Student Module (Proof of Concept)
SCS2303 Software Architecture - Assignment 3, Group 26
Author: Krishan (Student Module)

No database is used - all data lives in in-memory data structures and is
seeded with hardcoded sample values. Run this file directly to see a demo
of all four student-facing interfaces.

===========================================================================
DESIGN PATTERNS USED IN THIS MODULE
===========================================================================
1. SINGLETON (Creational)
   Where : CourseCatalog
   Why   : The whole application must share exactly ONE in-memory course
           data store. If every component created its own catalog, seat
           counts and enrolments would go out of sync. Singleton guarantees
           a single source of truth without passing the instance around
           everywhere manually.

2. STRATEGY (Behavioral)
   Where : SearchStrategy family (SearchByDepartment, SearchByKeyword,
           SearchByInstructor, SearchByCourseNumber) used by
           CourseCatalogBrowser
   Why   : "Course Catalogue Browse" requires searching by department,
           course number, keyword, or instructor. Instead of one method
           full of if/elif branches (violates Open/Closed Principle), each
           search algorithm is its own class. CourseCatalogBrowser just
           delegates to whichever strategy is plugged in, and a new search
           type can be added later without touching existing code.

3. CHAIN OF RESPONSIBILITY (Behavioral)
   Where : EnrollmentValidator family (PrerequisiteValidator ->
           CapacityValidator -> TimeConflictValidator)
   Why   : The spec's enrolment use case explicitly describes an ordered
           sequence of checks (prerequisites, then capacity, then time
           conflict), where the process should stop at the first failure.
           Chain of Responsibility maps directly onto this: each validator
           only knows how to do its own check and hands off to the next.
           New validation rules (e.g. a "hold on account" check) can be
           inserted into the chain without changing EnrollmentManager.

4. OBSERVER (Behavioral)
   Where : EnrollmentManager (Subject) notifies NotificationService
           (Observer) on SEAT_AVAILABLE and ADVISEE_DROPPED events
   Why   : The system-wide requirement explicitly says the notification
           mechanism "should be automated and decoupled from the core
           enrolment logic." Observer lets EnrollmentManager fire an event
           without knowing or caring who is listening or how a
           notification is actually delivered (email/SMS/push - the
           NotificationService here just prints, but could be swapped
           freely).

5. FACADE (Structural)
   Where : StudentService
   Why   : The four interfaces (browse, enrol, schedule, progress) are
           each backed by their own class with their own responsibility
           (Single Responsibility Principle). StudentService gives the
           presentation layer / test harness ONE simple, unified API so it
           doesn't need to know about CourseCatalogBrowser,
           EnrollmentManager, ScheduleManager and ProgressTracker
           individually.

SOLID principles are applied throughout, e.g.:
- Single Responsibility : each *Validator, the browser, the schedule
  manager and the progress tracker each do exactly one job.
- Open/Closed            : new search strategies or validators can be
  added as new classes without editing existing ones.
- Liskov Substitution    : any SearchStrategy / EnrollmentValidator /
  Observer subclass can be substituted wherever the base type is expected.
- Dependency Inversion   : EnrollmentManager and CourseCatalogBrowser
  depend on the SearchStrategy / EnrollmentValidator abstractions, not on
  concrete search or validation logic.
===========================================================================
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Dict, Optional


# ===========================================================================
# DOMAIN MODELS
# ===========================================================================

@dataclass
class Schedule:
    days: List[str]          # e.g. ["Mon", "Wed"]
    start_time: str          # 24hr "HH:MM"
    end_time: str
    location: str

    def overlaps(self, other: "Schedule") -> bool:
        """Two schedules overlap if they share a day AND their time ranges intersect."""
        if not set(self.days) & set(other.days):
            return False
        return not (self.end_time <= other.start_time or other.end_time <= self.start_time)

    def __str__(self):
        return f"{'/'.join(self.days)} {self.start_time}-{self.end_time} @ {self.location}"


@dataclass
class Course:
    course_id: str
    name: str
    description: str
    department: str
    instructor: str
    capacity: int
    schedule: Schedule
    prerequisites: List[str] = field(default_factory=list)
    enrolled_student_ids: List[str] = field(default_factory=list)
    waitlisted_student_ids: List[str] = field(default_factory=list)

    @property
    def available_seats(self) -> int:
        return self.capacity - len(self.enrolled_student_ids)

    def is_full(self) -> bool:
        return self.available_seats <= 0


@dataclass
class Student:
    student_id: str
    name: str
    advisor: str
    completed_courses: Dict[str, str] = field(default_factory=dict)   # course_id -> grade
    enrolled_course_ids: List[str] = field(default_factory=list)
    waitlisted_course_ids: List[str] = field(default_factory=list)


@dataclass
class DegreeProgram:
    name: str
    required_course_ids: List[str]


# ===========================================================================
# PATTERN 1: SINGLETON - CourseCatalog
# ===========================================================================

class CourseCatalog:
    """Single shared in-memory store of all courses. __new__ is overridden so
    that every call to CourseCatalog() anywhere in the app returns the exact
    same object, seeded only once."""

    _instance: Optional["CourseCatalog"] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._courses = {}
            cls._instance._seed_sample_data()
        return cls._instance

    def _seed_sample_data(self):
        self._courses: Dict[str, Course] = {
            "CS101": Course(
                "CS101", "Introduction to Programming",
                "Fundamentals of programming using Python.",
                "CS", "Dr. Perera", capacity=2,
                schedule=Schedule(["Mon", "Wed"], "09:00", "10:30", "Room A1"),
            ),
            "CS150": Course(
                "CS150", "Intro to Web Development",
                "Building basic web pages with HTML/CSS/JS.",
                "CS", "Dr. Gunawardena", capacity=40,
                schedule=Schedule(["Mon", "Wed"], "09:00", "10:30", "Room A2"),
                # NOTE: deliberately clashes with CS101's time slot, to
                # demonstrate the TimeConflictValidator below.
            ),
            "CS201": Course(
                "CS201", "Data Structures and Algorithms",
                "Core data structures, complexity analysis and algorithms.",
                "CS", "Dr. Silva", capacity=1,
                schedule=Schedule(["Tue", "Thu"], "11:00", "12:30", "Room B1"),
                prerequisites=["CS101"],
            ),
            "CS301": Course(
                "CS301", "Software Architecture",
                "Architectural and design patterns for large systems.",
                "CS", "Dr. Fernando", capacity=30,
                schedule=Schedule(["Tue", "Thu"], "13:00", "14:30", "Room B2"),
                prerequisites=["CS201"],
            ),
            "MATH101": Course(
                "MATH101", "Calculus I",
                "Limits, derivatives and integrals.",
                "MATH", "Dr. Jayasuriya", capacity=50,
                schedule=Schedule(["Tue", "Thu"], "08:00", "09:30", "Room C1"),
            ),
        }

    def get_course(self, course_id: str) -> Optional[Course]:
        return self._courses.get(course_id)

    def all_courses(self) -> List[Course]:
        return list(self._courses.values())


# ===========================================================================
# PATTERN 2: STRATEGY - course search
# ===========================================================================

class SearchStrategy(ABC):
    @abstractmethod
    def search(self, courses: List[Course], term: str) -> List[Course]:
        ...


class SearchByDepartment(SearchStrategy):
    def search(self, courses, term):
        return [c for c in courses if c.department.lower() == term.lower()]


class SearchByKeyword(SearchStrategy):
    def search(self, courses, term):
        term = term.lower()
        return [c for c in courses if term in c.name.lower() or term in c.description.lower()]


class SearchByInstructor(SearchStrategy):
    def search(self, courses, term):
        return [c for c in courses if term.lower() in c.instructor.lower()]


class SearchByCourseNumber(SearchStrategy):
    def search(self, courses, term):
        return [c for c in courses if term.lower() in c.course_id.lower()]


class CourseCatalogBrowser:
    """Interface 1: Course Catalogue Browse. Delegates the actual matching
    logic to whichever SearchStrategy is currently set (Strategy pattern)."""

    def __init__(self, catalog: CourseCatalog, strategy: SearchStrategy = None):
        self._catalog = catalog
        self._strategy: SearchStrategy = strategy or SearchByKeyword()

    def set_strategy(self, strategy: SearchStrategy) -> None:
        self._strategy = strategy

    def browse(self, term: str = "") -> List[Course]:
        courses = self._catalog.all_courses()
        if not term:
            return courses
        return self._strategy.search(courses, term)


# ===========================================================================
# OBSERVER - decoupled notifications
# ===========================================================================

class Observer(ABC):
    @abstractmethod
    def update(self, event: str, **kwargs) -> None:
        ...


class NotificationService(Observer):
    """Concrete Observer. Stands in for a real email/SMS gateway - here it
    just prints, but EnrollmentManager never needs to know that."""

    def update(self, event: str, **kwargs) -> None:
        if event == "SEAT_AVAILABLE":
            print(f"  [NOTIFY] {kwargs['student_name']}: a seat opened up in "
                  f"{kwargs['course_name']} - you have been moved off the waitlist.")
        elif event == "ADVISEE_DROPPED":
            print(f"  [NOTIFY] Advisor {kwargs['advisor']}: your advisee {kwargs['student_name']} "
                  f"dropped {kwargs['course_name']}.")


class Subject(ABC):
    def __init__(self):
        self._observers: List[Observer] = []

    def attach(self, observer: Observer) -> None:
        self._observers.append(observer)

    def detach(self, observer: Observer) -> None:
        if observer in self._observers:
            self._observers.remove(observer)

    def notify(self, event: str, **kwargs) -> None:
        for obs in self._observers:
            obs.update(event, **kwargs)


# ===========================================================================
# PATTERN 3: CHAIN OF RESPONSIBILITY - enrolment validation
# ===========================================================================

class ValidationResult:
    def __init__(self, ok: bool, reason: str = ""):
        self.ok = ok
        self.reason = reason

    def __bool__(self):
        return self.ok


class EnrollmentValidator(ABC):
    """Base handler. Each concrete validator performs ONE check and, if it
    passes, forwards the request to the next handler in the chain."""

    def __init__(self):
        self._next: Optional["EnrollmentValidator"] = None

    def set_next(self, validator: "EnrollmentValidator") -> "EnrollmentValidator":
        self._next = validator
        return validator  # allows fluent chaining: a.set_next(b).set_next(c)

    def validate(self, student: Student, course: Course) -> ValidationResult:
        result = self._check(student, course)
        if not result.ok:
            return result
        if self._next:
            return self._next.validate(student, course)
        return ValidationResult(True)

    @abstractmethod
    def _check(self, student: Student, course: Course) -> ValidationResult:
        ...


class PrerequisiteValidator(EnrollmentValidator):
    def _check(self, student, course):
        missing = [p for p in course.prerequisites if p not in student.completed_courses]
        if missing:
            return ValidationResult(False, f"Missing prerequisite(s): {', '.join(missing)}")
        return ValidationResult(True)


class CapacityValidator(EnrollmentValidator):
    def _check(self, student, course):
        if course.is_full():
            return ValidationResult(False, f"{course.course_id} is at full capacity")
        return ValidationResult(True)


class TimeConflictValidator(EnrollmentValidator):
    def __init__(self, catalog: CourseCatalog):
        super().__init__()
        self._catalog = catalog

    def _check(self, student, course):
        for cid in student.enrolled_course_ids:
            other = self._catalog.get_course(cid)
            if other and other.schedule.overlaps(course.schedule):
                return ValidationResult(False, f"Time conflict with already-enrolled {other.course_id}")
        return ValidationResult(True)


# ===========================================================================
# Interface 2: Registration and Enrolment
# ===========================================================================

class EnrollmentManager(Subject):
    """Runs each enrol/drop request through the validation chain, applies
    the (all-or-nothing) state change, and fires Observer notifications."""

    def __init__(self, catalog: CourseCatalog):
        super().__init__()
        self._catalog = catalog
        self._chain = self._build_chain()

    def _build_chain(self) -> EnrollmentValidator:
        prereq = PrerequisiteValidator()
        capacity = CapacityValidator()
        conflict = TimeConflictValidator(self._catalog)
        prereq.set_next(capacity).set_next(conflict)
        return prereq

    def enroll(self, student: Student, course_id: str) -> ValidationResult:
        course = self._catalog.get_course(course_id)
        if not course:
            return ValidationResult(False, "Course not found")
        if course_id in student.enrolled_course_ids:
            return ValidationResult(False, "Already enrolled in this course")

        result = self._chain.validate(student, course)
        if not result.ok:
            return result

        # Transactional: both sides of the enrolment are updated together,
        # only after every validation step has already passed.
        course.enrolled_student_ids.append(student.student_id)
        student.enrolled_course_ids.append(course_id)
        return ValidationResult(True, f"Enrolled in {course_id} successfully")

    def join_waitlist(self, student: Student, course_id: str) -> ValidationResult:
        course = self._catalog.get_course(course_id)
        if not course:
            return ValidationResult(False, "Course not found")
        if student.student_id in course.waitlisted_student_ids:
            return ValidationResult(False, "Already on the waitlist")
        course.waitlisted_student_ids.append(student.student_id)
        student.waitlisted_course_ids.append(course_id)
        return ValidationResult(True, f"Added to waitlist for {course_id}")

    def drop(self, student: Student, course_id: str) -> ValidationResult:
        course = self._catalog.get_course(course_id)
        if not course or course_id not in student.enrolled_course_ids:
            return ValidationResult(False, "Not currently enrolled in this course")

        course.enrolled_student_ids.remove(student.student_id)
        student.enrolled_course_ids.remove(course_id)

        # Decoupled notification: EnrollmentManager just announces the
        # events, it has no idea NotificationService exists.
        if course.waitlisted_student_ids:
            next_student_id = course.waitlisted_student_ids.pop(0)
            self.notify("SEAT_AVAILABLE", student_name=next_student_id, course_name=course.name)

        self.notify("ADVISEE_DROPPED", student_name=student.name,
                    advisor=student.advisor, course_name=course.name)

        return ValidationResult(True, f"Dropped {course_id} successfully")


# ===========================================================================
# Interface 3: Personal Schedule Management
# ===========================================================================

class ScheduleManager:
    def __init__(self, catalog: CourseCatalog):
        self._catalog = catalog

    def get_weekly_schedule(self, student: Student) -> Dict[str, List[Course]]:
        weekly: Dict[str, List[Course]] = {d: [] for d in ["Mon", "Tue", "Wed", "Thu", "Fri"]}
        for cid in student.enrolled_course_ids:
            course = self._catalog.get_course(cid)
            if course:
                for day in course.schedule.days:
                    weekly.setdefault(day, []).append(course)
        return weekly

    def print_schedule(self, student: Student) -> None:
        weekly = self.get_weekly_schedule(student)
        print(f"  Weekly schedule for {student.name}:")
        for day, courses in weekly.items():
            if courses:
                for c in courses:
                    print(f"    {day}: {c.course_id} {c.name} ({c.schedule.start_time}-{c.schedule.end_time}, {c.schedule.location})")


# ===========================================================================
# Interface 4: Academic Progress Tracking
# ===========================================================================

class ProgressTracker:
    def __init__(self, catalog: CourseCatalog):
        self._catalog = catalog

    def get_progress(self, student: Student, program: DegreeProgram) -> dict:
        completed = set(student.completed_courses.keys())
        required = set(program.required_course_ids)
        remaining = required - completed
        percent = round(len(completed & required) / len(required) * 100, 1) if required else 100.0
        return {
            "program": program.name,
            "completed_courses": dict(student.completed_courses),
            "remaining_required": sorted(remaining),
            "percent_complete": percent,
        }


# ===========================================================================
# PATTERN 5: FACADE - unified entry point for the four interfaces
# ===========================================================================

class StudentService:
    """Single simplified API the presentation layer / test harness talks to.
    Wires up the Singleton catalog, the Strategy-based browser, the Chain-
    of-Responsibility-backed enrollment manager (with its Observer attached),
    the schedule manager and the progress tracker."""

    def __init__(self):
        self.catalog = CourseCatalog()
        self.browser = CourseCatalogBrowser(self.catalog)
        self.enrollment = EnrollmentManager(self.catalog)
        self.schedule_mgr = ScheduleManager(self.catalog)
        self.progress_tracker = ProgressTracker(self.catalog)
        self.enrollment.attach(NotificationService())

    # Interface 1
    def browse_courses(self, term: str = "", strategy: SearchStrategy = None) -> List[Course]:
        if strategy:
            self.browser.set_strategy(strategy)
        return self.browser.browse(term)

    # Interface 2
    def enroll_student(self, student: Student, course_id: str) -> ValidationResult:
        return self.enrollment.enroll(student, course_id)

    def join_waitlist(self, student: Student, course_id: str) -> ValidationResult:
        return self.enrollment.join_waitlist(student, course_id)

    def drop_course(self, student: Student, course_id: str) -> ValidationResult:
        return self.enrollment.drop(student, course_id)

    # Interface 3
    def view_schedule(self, student: Student) -> Dict[str, List[Course]]:
        return self.schedule_mgr.get_weekly_schedule(student)

    # Interface 4
    def view_progress(self, student: Student, program: DegreeProgram) -> dict:
        return self.progress_tracker.get_progress(student, program)


# ===========================================================================
# DEMO / MAIN - simulates the student user stories from the assignment brief
# ===========================================================================

def line(title: str) -> None:
    print(f"\n--- {title} ---")


def main():
    service = StudentService()

    # Hardcoded sample students (no database - stored in a plain dict)
    students = {
        "S001": Student("S001", "Kasun Perera", advisor="Dr. Wickramasinghe",
                         completed_courses={"CS101": "A"}),
        "S002": Student("S002", "Nimal Jayawardena", advisor="Dr. Wickramasinghe"),
    }
    program = DegreeProgram("BSc in Computer Science",
                             required_course_ids=["CS101", "CS201", "CS301", "MATH101"])

    # --- Interface 1: Course Catalogue Browse -----------------------------
    line("Browse: all CS department courses (SearchByDepartment)")
    for c in service.browse_courses("CS", SearchByDepartment()):
        print(f"  {c.course_id}: {c.name} - {c.instructor} - {c.available_seats}/{c.capacity} seats")

    line("Browse: keyword 'algorithm' (SearchByKeyword)")
    for c in service.browse_courses("algorithm", SearchByKeyword()):
        print(f"  {c.course_id}: {c.name}")

    # --- Interface 2: Registration and Enrolment ---------------------------
    line("Nimal (S002) tries to enrol in CS201 without completing CS101")
    result = service.enroll_student(students["S002"], "CS201")
    print(f"  Result: {result.ok} - {result.reason}")

    line("Kasun (S001) enrols in CS201 (has completed CS101, 1 seat available)")
    result = service.enroll_student(students["S001"], "CS201")
    print(f"  Result: {result.ok} - {result.reason}")

    line("Nimal (S002) is missing prerequisites; simulate having completed CS101 too, then try again - now capacity is full")
    students["S002"].completed_courses["CS101"] = "B"
    result = service.enroll_student(students["S002"], "CS201")
    print(f"  Result: {result.ok} - {result.reason}")
    if not result.ok:
        wl = service.join_waitlist(students["S002"], "CS201")
        print(f"  Waitlist result: {wl.ok} - {wl.reason}")

    line("Kasun enrols in CS101, then tries CS150 which clashes in time -> TimeConflictValidator")
    service.enroll_student(students["S001"], "CS101")
    result = service.enroll_student(students["S001"], "CS150")
    print(f"  Result: {result.ok} - {result.reason}")

    line("Kasun drops CS201 -> Observer notifies waitlisted Nimal + advisor (decoupled from core logic)")
    result = service.drop_course(students["S001"], "CS201")
    print(f"  Result: {result.ok} - {result.reason}")

    # --- Interface 3: Personal Schedule Management --------------------------
    line("Kasun's weekly schedule")
    service.schedule_mgr.print_schedule(students["S001"])

    # --- Interface 4: Academic Progress Tracking -----------------------------
    line("Nimal's academic progress toward BSc in Computer Science")
    progress = service.view_progress(students["S002"], program)
    print(f"  Completed: {progress['completed_courses']}")
    print(f"  Still required: {progress['remaining_required']}")
    print(f"  Percent complete: {progress['percent_complete']}%")


if __name__ == "__main__":
    main()