"""
nexusenroll/admin/data/repositories.py

Role: DATA TIER — Repository abstractions for the Administrator module.

Re-exports the abstract repository ports (CourseRepository,
ProgramRepository, StudentRepository, FacultyRepository,
AuditLogRepository) from the shared kernel so every Service Tier file
in this module can keep writing `from nexusenroll.admin.data.repositories
import CourseRepository` for its type hints (Dependency Inversion: the
Service Tier depends only on these abstractions, never on the
CSV-backed concrete classes). The concrete, CSV-backed instances
(CSVCourseRepository, etc.) are constructed exactly once, in
nexusenroll/system/app.py, and injected into this module's
build_facade() — no file in this module ever imports a concrete
repository class directly.
"""

from nexusenroll.common.repositories import (  # noqa: F401 (re-exported on purpose)
    CourseRepository,
    ProgramRepository,
    StudentRepository,
    FacultyRepository,
    AuditLogRepository,
)
