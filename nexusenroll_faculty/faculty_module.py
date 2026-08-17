"""
NexusEnroll - Faculty Service (SOA Proof of Concept)
SCS 2303 - Software Architecture Assignment 3

ARCHITECTURAL PATTERN: Service-Oriented Architecture (SOA)
------------------------------------------------------------
The system is decomposed into coarse-grained, independently deployable
SERVICES (FacultyService, and — in the full system — StudentService,
AdminService, NotificationService), each exposing a formal CONTRACT
(an abstract interface) as its only entry point. Services never call
each other's internals directly; instead they communicate through a
shared Enterprise Service Bus (ESB), which routes messages/events
between services. This differs from Microservices (fine-grained, each
with its own database and independent scaling) and from 3-Tier
(layers within a single app, not separately deployable services).

Why SOA fits NexusEnroll:
  - The university already has other enterprise systems (finance,
    HR/payroll, a future financial-aid system) that need to integrate
    with enrolment. An ESB is the standard SOA answer for plugging a
    new external system in without touching existing services.
  - Faculty, Student, and Admin functions are natural, coarse service
    boundaries — coarser than microservices would need for a single
    university, avoiding the operational overhead of running dozens
    of tiny services for a moderate-scale, single-organisation system.
  - Services can be reused by both the SPA and a future mobile app,
    since both just call the same service contracts over the bus/API
    gateway — satisfying the "same back-end for web and mobile"
    requirement.

This file implements the FACULTY SERVICE: its contract, its
implementation (business logic), and a lightweight in-process ESB
simulation so the proof-of-concept is runnable without external
infrastructure (a real deployment would swap ESBSimulator for an
actual bus product, e.g. Mule ESB, RabbitMQ, or an API gateway).

Design Patterns Used (within the Faculty service's internals)
---------------------------------------------------------------
1. STATE — Grade lifecycle: Draft -> Pending -> Submitted (or back to
   Draft on rejection). Each state enforces its own legal actions.
2. OBSERVER — Used to implement the ESB's publish/subscribe channel:
   FacultyService publishes domain events; other services (Registrar,
   Advisor, Admin) subscribe without FacultyService knowing about them.
   This is literally how an ESB behaves, so Observer models it well.
3. STRATEGY — Grade validation rules (Letter vs Numeric) are
   interchangeable strategy objects (Open/Closed Principle).
4. COMMAND — Batch grade submissions are wrapped as Command objects so
   a batch can partially succeed with clear, per-item error reporting
   (supports the assignment's transactional requirement).

The __main__ block simulates faculty user stories end-to-end via the
service contract and ESB, standing in for the presentation tier
(optional per the assignment).
"""

from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Optional


# ===========================================================================
# ESB (Enterprise Service Bus) — the SOA communication backbone
# ===========================================================================

class ServiceMessage:
    """A single message/event travelling on the bus. In a real SOA
    deployment this would typically be a SOAP/XML or JSON envelope
    with routing headers; here it's kept minimal for the PoC."""

    def __init__(self, event_type: str, source_service: str, payload: dict):
        self.event_type = event_type
        self.source_service = source_service
        self.payload = payload
        self.timestamp = datetime.now()


class ServiceEndpoint(ABC):
    """Contract every service that listens on the bus must implement.
    This is the ESB-side analogue of the Observer pattern's Observer
    role: the bus doesn't know what each service does with a message,
    only that it can receive one."""

    @abstractmethod
    def receive(self, message: ServiceMessage) -> None:
        ...


class EnterpriseServiceBus:
    """Simulates the ESB: services publish messages to named channels
    (event types) and other services subscribe to those channels. This
    is the mechanism that lets NexusEnroll plug in new services (e.g.
    a future Financial Aid System) without changing FacultyService —
    the new service just subscribes to the events it cares about."""

    def __init__(self) -> None:
        self._subscribers: Dict[str, List[ServiceEndpoint]] = {}

    def subscribe(self, event_type: str, endpoint: ServiceEndpoint) -> None:
        self._subscribers.setdefault(event_type, []).append(endpoint)

    def publish(self, message: ServiceMessage) -> None:
        for endpoint in self._subscribers.get(message.event_type, []):
            endpoint.receive(message)


# ===========================================================================
# Domain / value objects (shared vocabulary across services)
# ===========================================================================

@dataclass
class Student:
    student_id: str
    name: str
    email: str


@dataclass
class Course:
    course_code: str
    title: str
    capacity: int
    enrolled_students: List[Student] = field(default_factory=list)

    def roster(self) -> List[Student]:
        return list(self.enrolled_students)


@dataclass
class Faculty:
    faculty_id: str
    name: str
    email: str
    courses: List[Course] = field(default_factory=list)


# ===========================================================================
# STRATEGY PATTERN — pluggable grade validation schemes
# ===========================================================================

class GradeValidationStrategy(ABC):
    @abstractmethod
    def is_valid(self, value: str) -> bool:
        ...

    @abstractmethod
    def describe(self) -> str:
        ...


class LetterGradeStrategy(GradeValidationStrategy):
    VALID = {"A+", "A", "A-", "B+", "B", "B-", "C+", "C", "C-", "D", "F"}

    def is_valid(self, value: str) -> bool:
        return value.upper() in self.VALID

    def describe(self) -> str:
        return "Letter grade (A+ .. F)"


class NumericGradeStrategy(GradeValidationStrategy):
    def is_valid(self, value: str) -> bool:
        try:
            return 0 <= float(value) <= 100
        except ValueError:
            return False

    def describe(self) -> str:
        return "Numeric grade (0-100)"


# ===========================================================================
# STATE PATTERN — grade lifecycle
# ===========================================================================

class GradeState(ABC):
    @abstractmethod
    def submit(self, grade: "Grade") -> None: ...
    @abstractmethod
    def approve(self, grade: "Grade") -> None: ...
    @abstractmethod
    def reject(self, grade: "Grade", reason: str) -> None: ...
    @abstractmethod
    def edit(self, grade: "Grade", new_value: str) -> None: ...

    def name(self) -> str:
        return self.__class__.__name__.replace("State", "")


class DraftState(GradeState):
    def submit(self, grade: "Grade") -> None:
        grade.state = PendingState()
        print(f"  -> {grade.student.name}: Draft -> Pending")

    def approve(self, grade: "Grade") -> None:
        print("  !! Cannot approve a grade that hasn't been submitted yet.")

    def reject(self, grade: "Grade", reason: str) -> None:
        print("  !! Cannot reject a grade still in Draft.")

    def edit(self, grade: "Grade", new_value: str) -> None:
        grade.value = new_value
        print(f"  -> Draft grade for {grade.student.name} edited to '{new_value}'")


class PendingState(GradeState):
    def submit(self, grade: "Grade") -> None:
        print("  !! Grade already pending review.")

    def approve(self, grade: "Grade") -> None:
        grade.state = SubmittedState()
        print(f"  -> {grade.student.name}: Pending -> Submitted")

    def reject(self, grade: "Grade", reason: str) -> None:
        grade.state = DraftState()
        grade.rejection_reason = reason
        print(f"  -> {grade.student.name}: rejected ('{reason}'), back to Draft")

    def edit(self, grade: "Grade", new_value: str) -> None:
        print("  !! Cannot edit while pending; reject it first.")


class SubmittedState(GradeState):
    def submit(self, grade: "Grade") -> None:
        print("  !! Already submitted.")

    def approve(self, grade: "Grade") -> None:
        print("  !! Already approved/submitted.")

    def reject(self, grade: "Grade", reason: str) -> None:
        print("  !! Cannot reject a finalised grade.")

    def edit(self, grade: "Grade", new_value: str) -> None:
        print("  !! Cannot edit a finalised (Submitted) grade.")


@dataclass
class Grade:
    student: Student
    course_code: str
    value: str
    state: GradeState = field(default_factory=DraftState)
    rejection_reason: Optional[str] = None

    def status(self) -> str:
        return self.state.name()


# ===========================================================================
# COMMAND PATTERN — batch grade submission
# ===========================================================================

class Command(ABC):
    @abstractmethod
    def execute(self) -> bool: ...


class SubmitGradeCommand(Command):
    def __init__(self, grade: Grade, strategy: GradeValidationStrategy):
        self.grade = grade
        self.strategy = strategy

    def execute(self) -> bool:
        if not self.strategy.is_valid(self.grade.value):
            return False
        self.grade.state.submit(self.grade)
        return True


# ===========================================================================
# SERVICE CONTRACT — what the Faculty Service exposes to the rest of the SOA
# ===========================================================================

class IFacultyService(ABC):
    """The formal service contract. In a real SOA deployment this would
    be described in WSDL (SOAP) or an OpenAPI spec (REST) and published
    to a service registry so other services/clients can discover it.
    Consumers (the SPA, mobile app, or other services via the ESB) only
    ever depend on this interface — never on FacultyServiceImpl directly."""

    @abstractmethod
    def view_roster(self, course_code: str) -> List[Student]: ...

    @abstractmethod
    def submit_grades(self, course_code: str, strategy: GradeValidationStrategy) -> None: ...

    @abstractmethod
    def approve_grades(self, course_code: str) -> None: ...

    @abstractmethod
    def request_course_change(self, faculty: Faculty, course: Course, description: str) -> None: ...


# ===========================================================================
# FACULTY SERVICE — implementation, registered on the ESB
# ===========================================================================

class FacultyServiceImpl(IFacultyService, ServiceEndpoint):
    """Concrete Faculty Service. Owns its own data (grades, courses) —
    per SOA practice, other services never reach into this data
    directly; they only see what's published on the bus."""

    SERVICE_NAME = "FacultyService"

    def __init__(self, bus: EnterpriseServiceBus):
        self.bus = bus
        self.courses: Dict[str, Course] = {}
        self.grades: Dict[str, Dict[str, Grade]] = {}  # course_code -> student_id -> Grade
        self.bus.subscribe("course_change_response", self)  # e.g. admin approves/rejects

    def register_course(self, course: Course) -> None:
        self.courses[course.course_code] = course
        self.grades.setdefault(course.course_code, {})

    # --- IFacultyService ---------------------------------------------

    def view_roster(self, course_code: str) -> List[Student]:
        return self.courses[course_code].roster()

    def record_draft_grade(self, course_code: str, student: Student, value: str) -> Grade:
        grade = Grade(student=student, course_code=course_code, value=value)
        self.grades[course_code][student.student_id] = grade
        return grade

    def submit_grades(self, course_code: str, strategy: GradeValidationStrategy) -> None:
        succeeded, failed = [], []
        for grade in self.grades[course_code].values():
            if grade.status() != "Draft":
                continue
            if SubmitGradeCommand(grade, strategy).execute():
                succeeded.append(grade)
            else:
                failed.append(grade)
                self.bus.publish(ServiceMessage(
                    "grade_submission_error", self.SERVICE_NAME,
                    {"course_code": course_code,
                     "error": f"Invalid grade '{grade.value}' for {grade.student.name} "
                              f"(expected {strategy.describe()})"},
                ))

        if succeeded:
            self.bus.publish(ServiceMessage(
                "grades_submitted", self.SERVICE_NAME,
                {"course_code": course_code, "count": len(succeeded)},
            ))

        print(f"  [FacultyService] Batch for {course_code}: {len(succeeded)} submitted, "
              f"{len(failed)} failed validation.")

    def approve_grades(self, course_code: str) -> None:
        for grade in self.grades[course_code].values():
            if grade.status() == "Pending":
                grade.state.approve(grade)

    def request_course_change(self, faculty: Faculty, course: Course, description: str) -> None:
        print(f"  [FacultyService] {faculty.name} requests change on "
              f"{course.course_code}: \"{description}\"")
        self.bus.publish(ServiceMessage(
            "course_change_requested", self.SERVICE_NAME,
            {"course_code": course.course_code, "faculty_name": faculty.name,
             "description": description},
        ))

    # --- ServiceEndpoint (receiving messages FROM other services) ----

    def receive(self, message: ServiceMessage) -> None:
        if message.event_type == "course_change_response":
            decision = message.payload.get("decision")
            print(f"  [FacultyService] Received admin decision on "
                  f"{message.payload['course_code']}: {decision}")


# ===========================================================================
# Other services on the bus (stubs — full implementations live in
# StudentService / AdminService / NotificationService modules)
# ===========================================================================

class RegistrarService(ServiceEndpoint):
    def receive(self, message: ServiceMessage) -> None:
        if message.event_type == "grades_submitted":
            print(f"  [RegistrarService] Updating academic records for "
                  f"{message.payload['course_code']} "
                  f"({message.payload['count']} students).")


class AdvisorNotificationService(ServiceEndpoint):
    def receive(self, message: ServiceMessage) -> None:
        if message.event_type == "grades_submitted":
            print(f"  [AdvisorNotificationService] Advisors notified: "
                  f"grades posted for {message.payload['course_code']}.")
        elif message.event_type == "course_change_requested":
            print(f"  [AdvisorNotificationService] Advisors notified: "
                  f"change requested for {message.payload['course_code']}.")


class AdminService(ServiceEndpoint):
    """Stands in for the real AdminService. Reacts to faculty course
    change requests by approving them, then publishes its decision
    back onto the bus — showing two services collaborating purely
    through the ESB, with neither calling the other directly."""

    def __init__(self, bus: EnterpriseServiceBus):
        self.bus = bus

    def receive(self, message: ServiceMessage) -> None:
        if message.event_type == "grade_submission_error":
            print(f"  [AdminService] Alert: {message.payload['error']}")
        elif message.event_type == "course_change_requested":
            print(f"  [AdminService] Reviewing request for "
                  f"{message.payload['course_code']}... approved.")
            self.bus.publish(ServiceMessage(
                "course_change_response", "AdminService",
                {"course_code": message.payload["course_code"], "decision": "APPROVED"},
            ))


# ===========================================================================
# Interactive CLI — takes real user input, stores it in arrays/lists as it
# goes. This stands in for the presentation tier (optional per the
# assignment) and is what you'd show running in the screencast.
# ===========================================================================

def run_interactive_demo() -> None:
    bus = EnterpriseServiceBus()

    faculty_service = FacultyServiceImpl(bus)
    bus.subscribe("grades_submitted", RegistrarService())
    bus.subscribe("grades_submitted", AdvisorNotificationService())
    bus.subscribe("course_change_requested", AdvisorNotificationService())

    admin_service = AdminService(bus)
    bus.subscribe("grade_submission_error", admin_service)
    bus.subscribe("course_change_requested", admin_service)

    # These two arrays/lists are populated live from user input below.
    students: List[Student] = []
    grade_inputs: List[tuple] = []  # (student, grade_value) pairs as entered

    print("=== NexusEnroll — Faculty Service (interactive demo) ===\n")

    faculty_name = input("Enter faculty name: ").strip() or "Dr. Perera"
    faculty_email = input("Enter faculty email: ").strip() or "perera@uni.edu"
    faculty = Faculty("F100", faculty_name, faculty_email, [])

    course_code = input("Enter course code (e.g. SCS2303): ").strip() or "SCS2303"
    course_title = input("Enter course title: ").strip() or "Software Architecture"
    try:
        capacity = int(input("Enter course capacity: ").strip())
    except ValueError:
        capacity = 60

    # --- Collect students into the `students` array ------------------
    try:
        n = int(input("\nHow many students to enrol? ").strip())
    except ValueError:
        n = 0

    for i in range(n):
        print(f"\n-- Student {i + 1} --")
        sid = input("  Student ID: ").strip() or f"S{i + 1:03d}"
        name = input("  Name: ").strip() or f"Student {i + 1}"
        email = input("  Email: ").strip() or f"{sid.lower()}@uni.edu"
        students.append(Student(sid, name, email))  # <-- stored in array

    course = Course(course_code, course_title, capacity, students)
    faculty.courses.append(course)
    faculty_service.register_course(course)

    print("\n=== Roster stored (from the `students` array) ===")
    for s in faculty_service.view_roster(course_code):
        print(f"  {s.student_id} - {s.name} ({s.email})")

    # --- Choose grading scheme (Strategy pattern) ---------------------
    scheme = input("\nGrading scheme — (L)etter or (N)umeric? [L]: ").strip().upper()
    strategy: GradeValidationStrategy = (
        NumericGradeStrategy() if scheme == "N" else LetterGradeStrategy()
    )
    print(f"Using: {strategy.describe()}")

    # --- Collect grades into the `grade_inputs` array, then into GradeBook
    print("\n=== Enter grades for each student ===")
    for s in students:
        value = input(f"  Grade for {s.name} ({s.student_id}): ").strip()
        grade_inputs.append((s, value))              # <-- stored in array
        faculty_service.record_draft_grade(course_code, s, value)

    print(f"\nCollected {len(grade_inputs)} grade entries: "
          f"{[(s.name, v) for s, v in grade_inputs]}")

    print("\n=== Submitting grades (Command batch, State transition, ESB events) ===")
    faculty_service.submit_grades(course_code, strategy)

    print("\n=== Approving all pending grades ===")
    faculty_service.approve_grades(course_code)

    print("\n=== Final grade report ===")
    for s in students:
        g = faculty_service.grades[course_code][s.student_id]
        print(f"  {s.name}: {g.value} [{g.status()}]")

    # --- Optional: course change request ------------------------------
    if input("\nSubmit a course change request? (y/n): ").strip().lower() == "y":
        description = input("  Describe the change: ").strip()
        faculty_service.request_course_change(faculty, course, description)


if __name__ == "__main__":
    run_interactive_demo()
