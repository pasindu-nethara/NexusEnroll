"""
nexusenroll/system/role_clis.py

Role: SYSTEM PRESENTATION TIER — thin, interactive, text-menu front
ends for the Student and Faculty services.

Per the assignment brief, "implementation of UI to interface the core
business tier logic is optional" — these classes exist to make the
system pleasant to drive interactively (and to record a screencast
of), but they contain NO business logic themselves. Every decision
(can this student enrol, is this grade valid, may this faculty member
view this roster) is made inside StudentService / FacultyServiceImpl;
these classes only collect input and print results, exactly the role
nexusenroll/admin/presentation/cli.py plays for the Administrator
module.
"""

from nexusenroll.common.repositories import StudentRepository, ProgramRepository, FacultyRepository


class StudentCLI:
    """Interactive menu for a single logged-in student, backed by the real StudentService."""

    def __init__(self, student_service, student_repo: StudentRepository, program_repo: ProgramRepository,
                 faculty_repo: FacultyRepository, student_service_module):
        self._service = student_service
        self._student_repo = student_repo
        self._program_repo = program_repo
        self._faculty_repo = faculty_repo
        self._sm = student_service_module  # gives access to the Strategy classes without re-importing them

    def run(self) -> None:
        student_id = input("Student ID (e.g. S001): ").strip()
        student = self._student_repo.get_by_id(student_id)
        if student is None:
            print("  Unknown student ID.")
            return

        while True:
            print(f"\n-- Student Menu ({student.name}) --")
            print(" a) Browse course catalogue")
            print(" b) Enrol in a course")
            print(" c) Drop a course")
            print(" d) View weekly schedule")
            print(" e) View academic progress")
            print(" 0) Log out")
            choice = input("Select an option: ").strip()
            if choice == "0":
                return
            elif choice == "a":
                self._browse()
            elif choice == "b":
                self._enroll(student)
            elif choice == "c":
                self._drop(student)
            elif choice == "d":
                self._service.schedule_mgr.print_schedule(student)
            elif choice == "e":
                self._progress(student)
            else:
                print("  Invalid option.")

    def _browse(self) -> None:
        term = input("  Search term (blank = list all): ").strip()
        mode = input("  Search by (d)epartment / (k)eyword / (i)nstructor / course (n)umber [k]: ").strip().lower()
        strategy = {
            "d": self._sm.SearchByDepartment(),
            "i": self._sm.SearchByInstructor(self._faculty_repo),
            "n": self._sm.SearchByCourseNumber(),
        }.get(mode, self._sm.SearchByKeyword())
        courses = self._service.browse_courses(term, strategy)
        if not courses:
            print("  No matching courses.")
        for c in courses:
            print(f"    {c.course_id}: {c.name} | {c.department} | "
                  f"{c.available_seats}/{c.capacity} seats | {c.schedule} | "
                  f"prereqs: {', '.join(c.prerequisites) or 'none'}")

    def _enroll(self, student) -> None:
        course_id = input("  Course ID to enrol in: ").strip()
        result = self._service.enroll_student(student, course_id)
        print(f"  {'OK' if result.ok else 'Failed'}: {result.reason}")
        if not result.ok and "full capacity" in result.reason.lower():
            if input("  Join the waitlist instead? (y/n): ").strip().lower() == "y":
                wl = self._service.join_waitlist(student, course_id)
                print(f"  {'OK' if wl.ok else 'Failed'}: {wl.reason}")

    def _drop(self, student) -> None:
        course_id = input("  Course ID to drop: ").strip()
        result = self._service.drop_course(student, course_id)
        print(f"  {'OK' if result.ok else 'Failed'}: {result.reason}")

    def _progress(self, student) -> None:
        if not student.program_id:
            print("  No degree program assigned to this student.")
            return
        program = self._program_repo.get_by_id(student.program_id)
        progress = self._service.view_progress(student, program)
        print(f"  Program: {progress['program']}")
        print(f"  Completed: {progress['completed_courses']}")
        print(f"  Still required: {progress['remaining_required']}")
        print(f"  Percent complete: {progress['percent_complete']}%")


class FacultyCLI:
    """Interactive menu for a single logged-in faculty member, backed by the real FacultyServiceImpl."""

    def __init__(self, faculty_service, faculty_repo: FacultyRepository, faculty_service_module):
        self._service = faculty_service
        self._faculty_repo = faculty_repo
        self._fm = faculty_service_module

    def run(self) -> None:
        faculty_id = input("Faculty ID (e.g. F001): ").strip()
        faculty = self._faculty_repo.get_by_id(faculty_id)
        if faculty is None:
            print("  Unknown faculty ID.")
            return

        while True:
            print(f"\n-- Faculty Menu ({faculty.name}) --")
            print(" a) View my courses")
            print(" b) View class roster")
            print(" c) Enter & submit grades for a course")
            print(" d) Approve pending grades for a course")
            print(" e) Request a course change")
            print(" 0) Log out")
            choice = input("Select an option: ").strip()
            if choice == "0":
                return
            elif choice == "a":
                self._list_courses(faculty)
            elif choice == "b":
                self._roster()
            elif choice == "c":
                self._submit_grades()
            elif choice == "d":
                self._approve_grades()
            elif choice == "e":
                self._request_change(faculty)
            else:
                print("  Invalid option.")

    def _list_courses(self, faculty) -> None:
        courses = self._service.list_courses_taught_by(faculty.faculty_id)
        if not courses:
            print("  No courses on record for this instructor.")
        for c in courses:
            print(f"    {c.course_id}: {c.name} | {c.enrolled_count}/{c.capacity} enrolled | {c.schedule}")

    def _roster(self) -> None:
        course_id = input("  Course ID: ").strip()
        try:
            roster = self._service.view_roster(course_id)
        except ValueError as exc:
            print(f"  {exc}")
            return
        if not roster:
            print("  No students enrolled.")
        for s in roster:
            print(f"    {s.student_id} - {s.name} ({s.email})")

    def _submit_grades(self) -> None:
        course_id = input("  Course ID: ").strip()
        try:
            roster = self._service.view_roster(course_id)
        except ValueError as exc:
            print(f"  {exc}")
            return
        scheme = input("  Grading scheme - (L)etter or (N)umeric? [L]: ").strip().upper()
        strategy = self._fm.NumericGradeStrategy() if scheme == "N" else self._fm.LetterGradeStrategy()
        for student in roster:
            value = input(f"    Grade for {student.name} ({student.student_id}): ").strip()
            self._service.record_draft_grade(course_id, student.student_id, value)
        self._service.submit_grades(course_id, strategy)

    def _approve_grades(self) -> None:
        course_id = input("  Course ID: ").strip()
        self._service.approve_grades(course_id)

    def _request_change(self, faculty) -> None:
        course_id = input("  Course ID: ").strip()
        course = self._service.course_repo.get_by_id(course_id)
        if course is None:
            print("  Course not found.")
            return
        description = input("  Describe the requested change: ").strip()
        self._service.request_course_change(faculty, course, description)
