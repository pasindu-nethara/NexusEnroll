"""
nexusenroll/system/app.py

Role: WHOLE-SYSTEM COMPOSITION ROOT — the "final software": wires the
three modules (student, faculty, admin) together into ONE running
NexusEnroll system, backed by the CSV files under data/.

This is the only file in the whole project that imports all three
modules at once. It:
  1. Builds ONE shared set of CSV-backed repositories (single source
     of truth — see nexusenroll/common/repositories.py), each loading
     its current state from data/*.csv on construction.
  2. Builds ONE shared Enterprise Service Bus (nexusenroll/common/esb.py).
  3. Constructs the REAL Administrator Facade
     (nexusenroll.admin.composition.build_facade), the REAL Student
     Service (nexusenroll.student.service.StudentService) and the REAL
     Faculty Service (nexusenroll.faculty.service.FacultyServiceImpl)
     on top of the shared repositories and bus.
  4. Registers the ESB subscribers from bus_hub.py that make the three
     services actually collaborate (course-change approval, grade ->
     transcript sync, system-wide notifications).
  5. Presents a small top-level "log in as..." menu so one person can
     drive all three modules against the SAME live system state in a
     single run — e.g. force-enrol a student as Administrator, then
     immediately see it on that student's schedule, then submit a
     grade as Faculty and see it appear in the student's progress
     report.

Persistence commit points: every repository loads once at startup and
keeps its working state in memory; save_all() rewrites every CSV file
from that state. It is called after each top-level menu action
returns (so the files reflect what just happened almost immediately)
and once more on exit, so a session's changes are never lost — see
save_all() below and its call sites in main().

There is exactly one way to run NexusEnroll: `python main.py` from the
repository root, which calls main() below.
"""

import os

from nexusenroll.common.repositories import (
    CSVCourseRepository,
    CSVProgramRepository,
    CSVStudentRepository,
    CSVFacultyRepository,
    CSVAuditLogRepository,
)
from nexusenroll.common.esb import EnterpriseServiceBus
from nexusenroll.common.notifications import ConsoleNotificationService

from nexusenroll.admin.composition import build_facade
from nexusenroll.admin.presentation.cli import AdminCLI

from nexusenroll.student import service as student_service_module
from nexusenroll.faculty import service as faculty_service_module

from nexusenroll.system.bus_hub import AdminServiceAdapter, RegistrarBridge, SystemNotificationHub
from nexusenroll.system.role_clis import StudentCLI, FacultyCLI


_SYSTEM_DIR = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(_SYSTEM_DIR))          # .../nexusenroll/system -> .../nexusenroll -> repo root
DATA_DIR = os.path.join(_ROOT, "data")


def build_system() -> dict:
    """Construct and wire the full, integrated NexusEnroll system on top of data/*.csv."""

    # --- ONE shared, CSV-backed data tier for all three services -------
    course_repo = CSVCourseRepository(os.path.join(DATA_DIR, "courses.csv"))
    program_repo = CSVProgramRepository(os.path.join(DATA_DIR, "programs.csv"))
    student_repo = CSVStudentRepository(os.path.join(DATA_DIR, "students.csv"))
    faculty_repo = CSVFacultyRepository(os.path.join(DATA_DIR, "faculty.csv"))
    audit_log_repo = CSVAuditLogRepository(os.path.join(DATA_DIR, "audit_log.csv"))

    # --- ONE shared ESB + notification sink ----------------------------
    bus = EnterpriseServiceBus()
    notifier = ConsoleNotificationService()

    # --- Administrator facade -------------------------------------------
    admin_facade = build_facade(
        course_repo=course_repo, program_repo=program_repo,
        student_repo=student_repo, faculty_repo=faculty_repo,
        audit_log_repo=audit_log_repo, notification_service=notifier,
        actor="admin",
    )

    # --- Student service --------------------------------------------------
    student_service_module.CourseCatalog.reset()  # drop any Singleton left over from a previous build_system() call
    student_service = student_service_module.StudentService(course_repo, faculty_repo, bus)

    # --- Faculty service -----------------------------------------------
    faculty_service = faculty_service_module.FacultyServiceImpl(bus, course_repo, student_repo)

    # --- Cross-service ESB subscribers (see bus_hub.py) ------------------
    admin_adapter = AdminServiceAdapter(bus, admin_facade)
    bus.subscribe("course_change_requested", admin_adapter)
    bus.subscribe("grade_submission_error", admin_adapter)

    registrar_bridge = RegistrarBridge(student_repo)
    bus.subscribe("grade_approved", registrar_bridge)

    notification_hub = SystemNotificationHub(notifier)
    for event_type in ("SEAT_AVAILABLE", "ADVISEE_DROPPED", "grades_submitted",
                        "course_change_requested", "grade_submission_error"):
        bus.subscribe(event_type, notification_hub)

    return {
        "bus": bus,
        "course_repo": course_repo,
        "program_repo": program_repo,
        "student_repo": student_repo,
        "faculty_repo": faculty_repo,
        "audit_log_repo": audit_log_repo,
        "admin_facade": admin_facade,
        "student_service": student_service,
        "faculty_service": faculty_service,
    }


def save_all(system: dict) -> None:
    """Persist every repository's current in-memory state back to its CSV file."""
    system["course_repo"].save()
    system["program_repo"].save()
    system["student_repo"].save()
    system["faculty_repo"].save()
    system["audit_log_repo"].save()


def main() -> None:
    system = build_system()

    student_cli = StudentCLI(
        system["student_service"], system["student_repo"], system["program_repo"],
        system["faculty_repo"], student_service_module,
    )
    faculty_cli = FacultyCLI(system["faculty_service"], system["faculty_repo"], faculty_service_module)
    admin_cli = AdminCLI(system["admin_facade"])

    print("=" * 70)
    print(" NexusEnroll — Integrated System")
    print(" (Student + Faculty + Administrator, one shared live system state)")
    print(f" Data stored in: {DATA_DIR}")
    print("=" * 70)
    print(" Sample logins seeded for this demo:")
    print("   Students : S001 Kasun, S002 Amaya, S003 Tharindu, S004 Nimal")
    print("   Faculty  : F001 Dr. Perera (CS), F002 Dr. Silva (Business), F003 Dr. Jayasuriya (Math)")

    menu = {"1": student_cli.run, "2": faculty_cli.run, "3": admin_cli.run}
    try:
        while True:
            print("\nLog in as:")
            print(" 1) Student")
            print(" 2) Faculty")
            print(" 3) Administrator")
            print(" 0) Exit NexusEnroll")
            choice = input("Select an option: ").strip()
            if choice == "0":
                break
            action = menu.get(choice)
            if action:
                action()
                save_all(system)  # commit point: persist whatever that session round-trip changed
            else:
                print("  Invalid option.")
    finally:
        save_all(system)
        print("Goodbye. All changes have been saved to data/*.csv.")
