"""
nexusenroll/admin/presentation/cli.py

Role: PRESENTATION TIER — CLI menu loop.

AdminCLI is the only class that talks directly to the user (input()/
print()) and the only class that talks to AdminFacade. It performs
basic input validation (e.g. "is this a valid integer") so the
program never crashes on bad input, but defers ALL business
validation (does this course exist, is this capacity valid, etc.) to
the Service Tier via AdminFacade — errors raised there are caught
here and shown as a friendly message, never as a raw traceback.
"""

from nexusenroll.admin.patterns.facade import AdminFacade
from nexusenroll.admin.presentation.formatters import render_table, render_report


class AdminCLI:
    """Interactive command-line menu for the Administrator module."""

    def __init__(self, facade: AdminFacade):
        self._facade = facade

    # ------------------------------------------------------------------
    # Input helpers (syntactic validation only — no business rules here)
    # ------------------------------------------------------------------

    @staticmethod
    def _prompt(label: str) -> str:
        return input(f"{label}: ").strip()

    @staticmethod
    def _prompt_int(label: str, default=None):
        raw = input(f"{label}{' [' + str(default) + ']' if default is not None else ''}: ").strip()
        if raw == "" and default is not None:
            return default
        try:
            return int(raw)
        except ValueError:
            print("  Please enter a whole number.")
            return None

    @staticmethod
    def _prompt_list(label: str) -> list:
        raw = input(f"{label} (comma-separated, blank for none): ").strip()
        if not raw:
            return []
        return [item.strip() for item in raw.split(",") if item.strip()]

    def _run_safely(self, action_description: str, fn, *args, **kwargs):
        """Run a facade call, catching business-rule errors so the CLI never crashes."""
        try:
            return fn(*args, **kwargs)
        except ValueError as exc:
            print(f"  [Error] Could not {action_description}: {exc}")
            return None
        except Exception as exc:  # noqa: BLE001 - CLI safety net for any unexpected error
            print(f"  [Unexpected error] {exc}")
            return None

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------

    def run(self):
        print("=" * 60)
        print(" NexusEnroll — Administrator Module (CLI)")
        print("=" * 60)
        menu_actions = {
            "1": self._menu_courses,
            "2": self._menu_programs,
            "3": self._menu_students,
            "4": self._menu_faculty,
            "5": self._menu_overrides,
            "6": self._menu_reports,
            "7": self._menu_audit_log,
        }
        while True:
            print("\nMain Menu:")
            print(" 1) Course Management")
            print(" 2) Program Management")
            print(" 3) Student Account Management")
            print(" 4) Faculty Account Management")
            print(" 5) Enrolment Overrides")
            print(" 6) Reports & Analytics")
            print(" 7) View Audit Log")
            print(" 0) Exit")
            choice = self._prompt("Select an option")
            if choice == "0":
                print("Goodbye.")
                break
            action = menu_actions.get(choice)
            if action:
                action()
            else:
                print("  Invalid option, please try again.")

    # ------------------------------------------------------------------
    # Course Management
    # ------------------------------------------------------------------

    def _menu_courses(self):
        print("\n-- Course Management --")
        print(" a) List courses")
        print(" b) Create course")
        print(" c) Edit course")
        print(" d) Delete course")
        choice = self._prompt("Select an option")
        if choice == "a":
            self._list_courses()
        elif choice == "b":
            self._create_course()
        elif choice == "c":
            self._edit_course()
        elif choice == "d":
            self._delete_course()
        else:
            print("  Invalid option.")

    def _list_courses(self):
        courses = self._facade.list_courses()
        rows = [{
            "ID": c.course_id, "Code": c.code, "Name": c.name,
            "Dept": c.department, "Enrolled/Cap": f"{c.enrolled_count}/{c.capacity}",
            "Schedule": c.schedule,
        } for c in courses]
        print("\n" + render_table(rows, "No courses found."))

    def _create_course(self):
        course_id = self._prompt("Course ID (unique)")
        code = self._prompt("Course code (e.g. CS101)")
        name = self._prompt("Course name")
        description = self._prompt("Description")
        department = self._prompt("Department")
        instructor_id = self._prompt("Instructor (faculty) ID")
        capacity = self._prompt_int("Capacity")
        if capacity is None:
            return
        schedule = self._prompt("Schedule (e.g. Mon/Wed 10:00-11:30, Room A2)")
        prerequisites = self._prompt_list("Prerequisite course codes")

        result = self._run_safely(
            "create course", self._facade.create_course,
            course_id=course_id, code=code, name=name, description=description,
            department=department, instructor_id=instructor_id, capacity=capacity,
            schedule=schedule, prerequisites=prerequisites,
        )
        if result:
            print(f"  Course '{result.code}' created successfully.")

    def _edit_course(self):
        course_id = self._prompt("Course ID to edit")
        print("  Leave a field blank to keep it unchanged.")
        updates = {}
        name = self._prompt("New name")
        if name:
            updates["name"] = name
        description = self._prompt("New description")
        if description:
            updates["description"] = description
        capacity_raw = input("New capacity: ").strip()
        if capacity_raw:
            try:
                updates["capacity"] = int(capacity_raw)
            except ValueError:
                print("  Capacity must be a number; skipping capacity update.")
        schedule = self._prompt("New schedule")
        if schedule:
            updates["schedule"] = schedule

        result = self._run_safely("edit course", self._facade.edit_course, course_id, **updates)
        if result:
            print(f"  Course '{result.course_id}' updated.")

    def _delete_course(self):
        course_id = self._prompt("Course ID to delete")
        result = self._run_safely("delete course", self._facade.delete_course, course_id)
        if result:
            print(f"  Course '{result.code}' deleted.")

    # ------------------------------------------------------------------
    # Program Management
    # ------------------------------------------------------------------

    def _menu_programs(self):
        print("\n-- Program Management --")
        print(" a) List programs")
        print(" b) Create program")
        print(" c) Edit program")
        choice = self._prompt("Select an option")
        if choice == "a":
            self._list_programs()
        elif choice == "b":
            self._create_program()
        elif choice == "c":
            self._edit_program()
        else:
            print("  Invalid option.")

    def _list_programs(self):
        programs = self._facade.list_programs()
        rows = [{
            "ID": p.program_id, "Name": p.name,
            "Required Courses": ", ".join(p.required_courses),
            "Total Credits": p.total_credits,
        } for p in programs]
        print("\n" + render_table(rows, "No programs found."))

    def _create_program(self):
        program_id = self._prompt("Program ID (unique)")
        name = self._prompt("Program name")
        required_courses = self._prompt_list("Required course codes")
        total_credits = self._prompt_int("Total credits", default=0)
        if total_credits is None:
            return
        result = self._run_safely(
            "create program", self._facade.create_program,
            program_id=program_id, name=name,
            required_courses=required_courses, total_credits=total_credits,
        )
        if result:
            print(f"  Program '{result.name}' created successfully.")

    def _edit_program(self):
        program_id = self._prompt("Program ID to edit")
        updates = {}
        name = self._prompt("New name (blank to keep)")
        if name:
            updates["name"] = name
        credits_raw = input("New total credits (blank to keep): ").strip()
        if credits_raw:
            try:
                updates["total_credits"] = int(credits_raw)
            except ValueError:
                print("  Credits must be a number; skipping.")
        result = self._run_safely("edit program", self._facade.edit_program, program_id, **updates)
        if result:
            print(f"  Program '{result.program_id}' updated.")

    # ------------------------------------------------------------------
    # Student Account Management
    # ------------------------------------------------------------------

    def _menu_students(self):
        print("\n-- Student Account Management --")
        print(" a) List students")
        print(" b) Add student")
        print(" c) Edit student")
        print(" d) Deactivate student")
        choice = self._prompt("Select an option")
        if choice == "a":
            self._list_students()
        elif choice == "b":
            self._add_student()
        elif choice == "c":
            self._edit_student()
        elif choice == "d":
            self._deactivate_student()
        else:
            print("  Invalid option.")

    def _list_students(self):
        students = self._facade.list_students()
        rows = [{
            "ID": s.student_id, "Name": s.name, "Email": s.email,
            "Program": s.program_id or "-", "Status": s.status.value,
            "Enrolled Courses": ", ".join(s.enrolled_course_ids) or "-",
        } for s in students]
        print("\n" + render_table(rows, "No students found."))

    def _add_student(self):
        account_id = self._prompt("Student ID (unique)")
        name = self._prompt("Name")
        email = self._prompt("Email")
        program_id = self._prompt("Program ID (blank if none)")
        result = self._run_safely(
            "add student", self._facade.add_student,
            account_id=account_id, name=name, email=email,
            program_id=program_id or None,
        )
        if result:
            print(f"  Student '{result.name}' added.")

    def _edit_student(self):
        student_id = self._prompt("Student ID to edit")
        updates = {}
        name = self._prompt("New name (blank to keep)")
        if name:
            updates["name"] = name
        email = self._prompt("New email (blank to keep)")
        if email:
            updates["email"] = email
        program_id = self._prompt("New program ID (blank to keep)")
        if program_id:
            updates["program_id"] = program_id
        result = self._run_safely("edit student", self._facade.edit_student, student_id, **updates)
        if result:
            print(f"  Student '{result.student_id}' updated.")

    def _deactivate_student(self):
        student_id = self._prompt("Student ID to deactivate")
        result = self._run_safely("deactivate student", self._facade.deactivate_student, student_id)
        if result:
            print(f"  Student '{student_id}' deactivated.")

    # ------------------------------------------------------------------
    # Faculty Account Management
    # ------------------------------------------------------------------

    def _menu_faculty(self):
        print("\n-- Faculty Account Management --")
        print(" a) List faculty")
        print(" b) Add faculty")
        print(" c) Edit faculty")
        print(" d) Deactivate faculty")
        choice = self._prompt("Select an option")
        if choice == "a":
            self._list_faculty()
        elif choice == "b":
            self._add_faculty()
        elif choice == "c":
            self._edit_faculty()
        elif choice == "d":
            self._deactivate_faculty()
        else:
            print("  Invalid option.")

    def _list_faculty(self):
        faculty = self._facade.list_faculty()
        rows = [{
            "ID": f.faculty_id, "Name": f.name, "Email": f.email,
            "Department": f.department, "Status": f.status.value,
        } for f in faculty]
        print("\n" + render_table(rows, "No faculty found."))

    def _add_faculty(self):
        account_id = self._prompt("Faculty ID (unique)")
        name = self._prompt("Name")
        email = self._prompt("Email")
        department = self._prompt("Department")
        result = self._run_safely(
            "add faculty", self._facade.add_faculty,
            account_id=account_id, name=name, email=email, department=department,
        )
        if result:
            print(f"  Faculty '{result.name}' added.")

    def _edit_faculty(self):
        faculty_id = self._prompt("Faculty ID to edit")
        updates = {}
        name = self._prompt("New name (blank to keep)")
        if name:
            updates["name"] = name
        email = self._prompt("New email (blank to keep)")
        if email:
            updates["email"] = email
        department = self._prompt("New department (blank to keep)")
        if department:
            updates["department"] = department
        result = self._run_safely("edit faculty", self._facade.edit_faculty, faculty_id, **updates)
        if result:
            print(f"  Faculty '{result.faculty_id}' updated.")

    def _deactivate_faculty(self):
        faculty_id = self._prompt("Faculty ID to deactivate")
        result = self._run_safely("deactivate faculty", self._facade.deactivate_faculty, faculty_id)
        if result:
            print(f"  Faculty '{faculty_id}' deactivated.")

    # ------------------------------------------------------------------
    # Enrolment Overrides
    # ------------------------------------------------------------------

    def _menu_overrides(self):
        print("\n-- Enrolment Overrides --")
        print("  Force-add a student into a course, bypassing prerequisite,")
        print("  capacity, and time-conflict checks.")
        student_id = self._prompt("Student ID")
        course_id = self._prompt("Course ID")
        result = self._run_safely("force-enrol student", self._facade.force_enrol, student_id, course_id)
        if result:
            print(f"  Student '{student_id}' force-enrolled into '{result.code}'.")

    # ------------------------------------------------------------------
    # Reports & Analytics
    # ------------------------------------------------------------------

    def _menu_reports(self):
        print("\n-- Reports & Analytics --")
        print(" a) Enrolment stats by department")
        print(" b) Faculty workload report")
        print(" c) Course popularity report (over capacity threshold)")
        choice = self._prompt("Select an option")
        if choice == "a":
            report = self._facade.enrolment_stats_report()
            print(render_report(report))
        elif choice == "b":
            report = self._facade.faculty_workload_report()
            print(render_report(report))
        elif choice == "c":
            threshold = self._prompt_int("Capacity threshold %", default=90)
            if threshold is None:
                return
            report = self._facade.course_popularity_report(float(threshold))
            print(render_report(report))
        else:
            print("  Invalid option.")

    # ------------------------------------------------------------------
    # Audit Log
    # ------------------------------------------------------------------

    def _menu_audit_log(self):
        entries = self._facade.get_audit_log()
        rows = [{
            "Time": e.timestamp, "Command": e.command_name,
            "Actor": e.actor, "Success": e.success, "Details": e.details,
        } for e in entries]
        print("\n" + render_table(rows, "No audit log entries yet."))
