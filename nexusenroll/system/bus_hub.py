"""
nexusenroll/system/bus_hub.py

Role: SYSTEM INTEGRATION TIER — the ESB subscribers that turn three
independently-authored modules into one coherent system.

Each class here is a ServiceEndpoint (see nexusenroll/common/esb.py)
that subscribes to one or more event types published by the Student
or Faculty service and reacts by calling into another service's real,
public contract — never into its private internals. This file is the
concrete embodiment of the assignment's requirement that the
notification mechanism be "automated and decoupled from the core
enrolment logic": neither nexusenroll.student.service nor
nexusenroll.faculty.service imports or even knows this file exists;
they only publish events and this file happens to be listening.

Three subscribers:
  - AdminServiceAdapter: routes Faculty course-change requests to the
    REAL Administrator facade (nexusenroll.admin) and relays its
    decision back onto the bus; also surfaces grade-submission errors
    to the admin office.
  - RegistrarBridge: when the Faculty service approves a grade, writes
    it into the SAME shared StudentRepository the Student service's
    Academic Progress Tracking reads from — this is what makes "grade
    posted by faculty -> visible in student's progress report" happen
    without Faculty and Student ever calling each other directly.
  - SystemNotificationHub: the single place that turns bus events into
    actual NotificationService.notify() calls, satisfying the
    system-wide Notification System requirement in one shared
    component instead of three modules each re-implementing delivery.
"""

from nexusenroll.common.esb import ServiceEndpoint, ServiceMessage, EnterpriseServiceBus
from nexusenroll.common.notifications import NotificationService
from nexusenroll.common.repositories import StudentRepository


class AdminServiceAdapter(ServiceEndpoint):
    """
    Stands in the "AdminService" role on the bus — backed by the REAL
    AdminFacade from nexusenroll.admin, shared with the rest of the
    integrated system.
    """

    SERVICE_NAME = "AdminService"

    def __init__(self, bus: EnterpriseServiceBus, admin_facade):
        self._bus = bus
        self._facade = admin_facade

    def receive(self, message: ServiceMessage) -> None:
        if message.event_type == "course_change_requested":
            course_id = message.payload["course_code"]
            course = self._facade.get_course(course_id)
            if course is None:
                decision = "REJECTED (course not found)"
            else:
                note = f" [Faculty request from {message.payload['faculty_name']}: {message.payload['description']}]"
                self._facade.edit_course(course_id, description=course.description + note)
                decision = "APPROVED"
            print(f"  [AdminService] Reviewed course-change request for {course_id}: {decision}")
            self._bus.publish(ServiceMessage(
                "course_change_response", self.SERVICE_NAME,
                {"course_code": course_id, "decision": decision},
            ))
        elif message.event_type == "grade_submission_error":
            print(f"  [AdminService] Alert relayed to admin office: {message.payload['error']}")


class RegistrarBridge(ServiceEndpoint):
    """
    Subscribes to "grade_approved" (published by FacultyServiceImpl
    once a grade reaches the Submitted state — see
    nexusenroll/faculty/service.py). Writes the final grade into the
    shared Student.completed_courses dict and removes the course from
    the student's *current* enrolled_course_ids, since a graded course
    is no longer "in progress". The Student service's own Academic
    Progress Tracking (ProgressTracker.get_progress) reads exactly
    this dict, so the update is visible there immediately — and is
    what data/students.csv will contain the next time the composition
    root saves the repositories.
    """

    def __init__(self, student_repo: StudentRepository):
        self._student_repo = student_repo

    def receive(self, message: ServiceMessage) -> None:
        if message.event_type != "grade_approved":
            return
        student = self._student_repo.get_by_id(message.payload["student_id"])
        if student is None:
            return
        course_id = message.payload["course_code"]
        student.completed_courses[course_id] = message.payload["value"]
        if course_id in student.enrolled_course_ids:
            student.enrolled_course_ids.remove(course_id)
        print(f"  [RegistrarBridge] {student.name}'s academic record updated: "
              f"{course_id} = {message.payload['value']}")


class SystemNotificationHub(ServiceEndpoint):
    """
    The single system-wide destination for "somebody needs to be told
    something" events raised by any service. Turns each event into one
    or more NotificationService.notify() calls. Because this is the
    ONLY class that calls notify(), swapping ConsoleNotificationService
    for a real EmailNotificationService later touches this one file.
    """

    def __init__(self, notifier: NotificationService):
        self._notifier = notifier

    def receive(self, message: ServiceMessage) -> None:
        p = message.payload
        if message.event_type == "SEAT_AVAILABLE":
            self._notifier.notify(
                p.get("student_id", p.get("student_name", "?")),
                f"A seat opened up in {p['course_name']} - you have been moved off the waitlist.",
            )
        elif message.event_type == "ADVISEE_DROPPED":
            self._notifier.notify(
                p.get("advisor") or "advising-office",
                f"Your advisee {p['student_name']} dropped {p['course_name']}.",
            )
        elif message.event_type == "grades_submitted":
            self._notifier.notify(
                "registrar",
                f"{p['count']} grade(s) submitted for {p['course_code']}, pending approval.",
            )
        elif message.event_type == "course_change_requested":
            self._notifier.notify(
                "admin-office",
                f"{p['faculty_name']} requested a change to {p['course_code']}: {p['description']}",
            )
        elif message.event_type == "grade_submission_error":
            self._notifier.notify("admin-office", f"ALERT: {p['error']}")
