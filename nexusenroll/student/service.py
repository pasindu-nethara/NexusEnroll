"""
nexusenroll/student/service.py — the Student Service.

Shared kernel: this file imports Course / Student / Schedule / Program
and the CourseRepository / FacultyRepository abstractions from
nexusenroll.common instead of declaring private copies, and its
CourseCatalog Singleton wraps a shared, CSV-backed CourseRepository
rather than a private dict. That is what makes this the REAL Student
Service in the integrated system (see nexusenroll/system/app.py): an
Administrator force-enrolling a student, or a Faculty member's roster,
are reading and writing the exact same Course/Student objects this
module's enrolment logic uses, and both end up persisted to the same
data/*.csv files.

===========================================================================
DESIGN PATTERNS USED IN THIS MODULE
===========================================================================
1. SINGLETON (Creational)
   Where : CourseCatalog
   Why   : The whole application must share exactly ONE in-memory course
           data view. If every component created its own catalog, seat
           counts and enrolments would go out of sync. Singleton guarantees
           a single source of truth without passing the instance around
           everywhere manually. (Here CourseCatalog additionally wraps a
           shared, CSV-backed CourseRepository, so the "single source of
           truth" is shared across the whole integrated system, not just
           within this module.)

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
           notification is actually delivered. NotificationService here
           both prints locally AND (if constructed with a reference to the
           shared EnterpriseServiceBus) republishes the same event onto the
           bus, so Faculty/Administrator-side subscribers can react too —
           the local Observer pattern is the origin of a system-wide SOA
           event, without EnrollmentManager knowing the bus exists.

5. FACADE (Structural)
   Where : StudentService
   Why   : The four interfaces (browse, enrol, schedule, progress) are
           each backed by their own class with their own responsibility
           (Single Responsibility Principle). StudentService gives the
           presentation layer / test harness ONE simple, unified API so it
           doesn't need to know about CourseCatalogBrowser,
           EnrollmentManager, ScheduleManager and ProgressTracker
           individually. This is also the object that is registered as the
           "StudentService" in the integrated system.

SOLID principles are applied throughout, e.g.:
- Single Responsibility : each *Validator, the browser, the schedule
  manager and the progress tracker each do exactly one job.
- Open/Closed            : new search strategies or validators can be
  added as new classes without editing existing ones.
- Liskov Substitution    : any SearchStrategy / EnrollmentValidator /
  Observer subclass can be substituted wherever the base type is expected.
- Dependency Inversion   : EnrollmentManager and CourseCatalogBrowser
  depend on the SearchStrategy / EnrollmentValidator abstractions, not on
  concrete search or validation logic; CourseCatalog depends on the
  CourseRepository abstraction, not on any particular storage technology.
===========================================================================
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Optional

from nexusenroll.common.domain import Course, Student, Program, Schedule, AccountStatus
from nexusenroll.common.esb import EnterpriseServiceBus, ServiceMessage
from nexusenroll.common.repositories import CourseRepository, FacultyRepository


# ===========================================================================
# PATTERN 1: SINGLETON - CourseCatalog
# ===========================================================================

class CourseCatalog:
    """
    Single shared course-data facade. __new__ is overridden so that
    every call to CourseCatalog() anywhere in the process returns the
    exact same object. The FIRST construction must be given the
    (CSV-backed) CourseRepository to wrap — every subsequent
    CourseCatalog() call, even with no arguments, reuses that same
    instance and its repository, exactly as the Singleton pattern
    intends.
    """

    _instance: Optional["CourseCatalog"] = None

    def __new__(cls, course_repo: Optional[CourseRepository] = None):
        if cls._instance is None:
            if course_repo is None:
                raise ValueError("CourseCatalog must be constructed with a course_repo the first time.")
            cls._instance = super().__new__(cls)
            cls._instance._repo = course_repo
        return cls._instance

    def get_course(self, course_id: str) -> Optional[Course]:
        return self._repo.get_by_id(course_id)

    def all_courses(self) -> List[Course]:
        return self._repo.get_all()

    @classmethod
    def reset(cls) -> None:
        """Test hook to drop the Singleton so a fresh repo can be attached."""
        cls._instance = None


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
    """
    Matches on either the instructor's faculty id (e.g. "F001") or, if
    a FacultyRepository was supplied, their display name (e.g.
    "Perera") — Course only stores instructor_id, so resolving a
    human-readable name requires looking the id up in the shared
    Faculty data, which is exactly the kind of cross-entity lookup a
    Strategy object can encapsulate without EnrollmentManager or
    CourseCatalogBrowser needing to know about Faculty at all.
    """

    def __init__(self, faculty_repo: Optional[FacultyRepository] = None):
        self._faculty_repo = faculty_repo

    def search(self, courses, term):
        term_l = term.lower()
        matches = []
        for c in courses:
            if term_l in c.instructor_id.lower():
                matches.append(c)
                continue
            if self._faculty_repo:
                faculty = self._faculty_repo.get_by_id(c.instructor_id)
                if faculty and term_l in faculty.name.lower():
                    matches.append(c)
        return matches


class SearchByCourseNumber(SearchStrategy):
    def search(self, courses, term):
        return [c for c in courses if term.lower() in c.course_id.lower()]


class CourseCatalogBrowser:
    """Interface 1: Course Catalogue Browse. Delegates the actual matching
    logic to whichever SearchStrategy is currently set (Strategy pattern)."""

    def __init__(self, catalog: CourseCatalog, strategy: SearchStrategy = None,
                 faculty_repo: Optional[FacultyRepository] = None):
        self._catalog = catalog
        self._faculty_repo = faculty_repo
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
    """
    Concrete Observer. Stands in for a real email/SMS gateway — here it
    prints locally, and if constructed with a reference to the shared
    EnterpriseServiceBus, ALSO republishes the same event onto the bus
    as a ServiceMessage, so subscribers in the Faculty and
    Administrator services (e.g. a real notification hub) can react
    too. EnrollmentManager never needs to know either of these things
    happen — it only ever calls notify() on whatever Observer is
    attached (Dependency Inversion).
    """

    def __init__(self, bus: Optional[EnterpriseServiceBus] = None):
        self._bus = bus

    def update(self, event: str, **kwargs) -> None:
        if event == "SEAT_AVAILABLE":
            print(f"  [NOTIFY] {kwargs['student_name']}: a seat opened up in "
                  f"{kwargs['course_name']} - you have been moved off the waitlist.")
        elif event == "ADVISEE_DROPPED":
            print(f"  [NOTIFY] Advisor {kwargs['advisor']}: your advisee {kwargs['student_name']} "
                  f"dropped {kwargs['course_name']}.")
        if self._bus is not None:
            self._bus.publish(ServiceMessage(event, "StudentService", kwargs))


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
        # events, it has no idea NotificationService (or the ESB behind
        # it) exists.
        if course.waitlisted_student_ids:
            next_student_id = course.waitlisted_student_ids.pop(0)
            self.notify("SEAT_AVAILABLE", student_id=next_student_id,
                        student_name=next_student_id, course_name=course.name)

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
            for c in courses:
                print(f"    {day}: {c.course_id} {c.name} ({c.schedule.start_time}-{c.schedule.end_time}, {c.schedule.location})")


# ===========================================================================
# Interface 4: Academic Progress Tracking
# ===========================================================================

class ProgressTracker:
    def __init__(self, catalog: CourseCatalog):
        self._catalog = catalog

    def get_progress(self, student: Student, program: Program) -> dict:
        completed = set(student.completed_courses.keys())
        required = set(program.required_courses)
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
    """
    Single simplified API the presentation layer / test harness talks to.
    Wires up the Singleton catalog, the Strategy-based browser, the Chain-
    of-Responsibility-backed enrollment manager (with its Observer attached),
    the schedule manager and the progress tracker — all on top of the
    SHARED, CSV-backed repositories passed in, so this is the real,
    integrated Student Service rather than a private sandbox.
    """

    def __init__(self, course_repo: CourseRepository, faculty_repo: Optional[FacultyRepository] = None,
                 bus: Optional[EnterpriseServiceBus] = None):
        self.catalog = CourseCatalog(course_repo)
        self.browser = CourseCatalogBrowser(self.catalog, faculty_repo=faculty_repo)
        self.enrollment = EnrollmentManager(self.catalog)
        self.schedule_mgr = ScheduleManager(self.catalog)
        self.progress_tracker = ProgressTracker(self.catalog)
        self.enrollment.attach(NotificationService(bus))

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
    def view_progress(self, student: Student, program: Program) -> dict:
        return self.progress_tracker.get_progress(student, program)
