"""
nexusenroll/faculty/service.py — the Faculty Service.

ARCHITECTURAL PATTERN: Service-Oriented Architecture (SOA)
------------------------------------------------------------
The system is decomposed into coarse-grained, independently reasoned
about SERVICES (FacultyService here, and — wired together in
nexusenroll/system/app.py — StudentService, AdminFacade, and a
Notification subsystem), each exposing a formal CONTRACT (an abstract
interface) as its only entry point. Services never call each other's
internals directly; instead they communicate through a shared
Enterprise Service Bus (ESB, see nexusenroll/common/esb.py), which
routes messages/events between services. This differs from
Microservices (fine-grained, each with its own database and
independent scaling) and from 3-Tier (layers within a single app, not
separately deployable services) — though this service is internally
organised in layers itself (data access via repositories, business
logic in FacultyServiceImpl), which is exactly the "combination of
patterns" the assignment explicitly allows.

Shared kernel: this file imports Course/Student/Faculty/Schedule and
the CourseRepository/StudentRepository abstractions from
nexusenroll.common instead of declaring its own private copies. That
is what makes this the REAL Faculty Service in the integrated system:
when it looks up a course's roster, it is reading the same,
CSV-persisted Course object the Student Service's enrolment logic and
the Administrator Facade's reports also read and write.

Design Patterns Used (within the Faculty service's internals)
---------------------------------------------------------------
1. STATE — Grade lifecycle: Draft -> Pending -> Submitted (or back to
   Draft on rejection). Each state enforces its own legal actions.
2. OBSERVER — Used to implement the ESB's publish/subscribe channel:
   FacultyService publishes domain events; other services (the
   integration layer's RegistrarBridge, AdminServiceAdapter,
   SystemNotificationHub) subscribe without FacultyService knowing
   about them. This is literally how an ESB behaves, so Observer
   models it well.
3. STRATEGY — Grade validation rules (Letter vs Numeric) are
   interchangeable strategy objects (Open/Closed Principle).
4. COMMAND — Batch grade submissions are wrapped as Command objects so
   a batch can partially succeed with clear, per-item error reporting
   (supports the assignment's transactional requirement).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Dict, Optional

from nexusenroll.common.domain import Student, Course, Faculty
from nexusenroll.common.esb import ServiceMessage, ServiceEndpoint, EnterpriseServiceBus
from nexusenroll.common.repositories import CourseRepository, StudentRepository


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
    """
    Concrete Faculty Service.

    Course and Student data are NOT privately owned here — they are
    read from the shared, CSV-backed CourseRepository /
    StudentRepository (the same instances the Student service and
    Administrator facade use), which is what keeps a roster viewed
    here in sync with who is actually enrolled via the Student service
    and who was force-enrolled via the Administrator facade. Grade
    records ARE privately owned by this service (per SOA practice,
    each service owns the data that is really "its" business) — other
    services only learn about them through the "grades_submitted" /
    "grade_approved" events published on the bus.
    """

    SERVICE_NAME = "FacultyService"

    def __init__(self, bus: EnterpriseServiceBus, course_repo: CourseRepository, student_repo: StudentRepository):
        self.bus = bus
        self.course_repo = course_repo
        self.student_repo = student_repo
        self.grades: Dict[str, Dict[str, Grade]] = {}  # course_code -> student_id -> Grade
        self.bus.subscribe("course_change_response", self)  # e.g. admin approves/rejects

    # --- IFacultyService ---------------------------------------------

    def _get_course(self, course_code: str) -> Course:
        course = self.course_repo.get_by_id(course_code)
        if course is None:
            raise ValueError(f"Course '{course_code}' not found.")
        return course

    def list_courses_taught_by(self, faculty_id: str) -> List[Course]:
        return [c for c in self.course_repo.get_all() if c.instructor_id == faculty_id]

    def view_roster(self, course_code: str) -> List[Student]:
        course = self._get_course(course_code)
        return [self.student_repo.get_by_id(sid) for sid in course.enrolled_student_ids]

    def record_draft_grade(self, course_code: str, student_id: str, value: str) -> Grade:
        student = self.student_repo.get_by_id(student_id)
        if student is None:
            raise ValueError(f"Student '{student_id}' not found.")
        grade = Grade(student=student, course_code=course_code, value=value)
        self.grades.setdefault(course_code, {})[student_id] = grade
        return grade

    def submit_grades(self, course_code: str, strategy: GradeValidationStrategy) -> None:
        succeeded, failed = [], []
        for grade in self.grades.get(course_code, {}).values():
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
                {"course_code": course_code, "count": len(succeeded),
                 "grades": [(g.student.student_id, g.value) for g in succeeded]},
            ))

        print(f"  [FacultyService] Batch for {course_code}: {len(succeeded)} submitted, "
              f"{len(failed)} failed validation.")

    def approve_grades(self, course_code: str) -> None:
        for grade in self.grades.get(course_code, {}).values():
            if grade.status() == "Pending":
                grade.state.approve(grade)
                self.bus.publish(ServiceMessage(
                    "grade_approved", self.SERVICE_NAME,
                    {"course_code": course_code, "student_id": grade.student.student_id,
                     "value": grade.value},
                ))

    def request_course_change(self, faculty: Faculty, course: Course, description: str) -> None:
        print(f"  [FacultyService] {faculty.name} requests change on "
              f"{course.course_id}: \"{description}\"")
        self.bus.publish(ServiceMessage(
            "course_change_requested", self.SERVICE_NAME,
            {"course_code": course.course_id, "faculty_name": faculty.name,
             "description": description},
        ))

    # --- ServiceEndpoint (receiving messages FROM other services) ----

    def receive(self, message: ServiceMessage) -> None:
        if message.event_type == "course_change_response":
            decision = message.payload.get("decision")
            print(f"  [FacultyService] Received admin decision on "
                  f"{message.payload['course_code']}: {decision}")
