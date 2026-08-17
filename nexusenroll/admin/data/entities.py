"""
nexusenroll/admin/data/entities.py

Role: DATA TIER — Entity (domain model) definitions for the
Administrator module.

Course / Program / Student / Faculty / AccountStatus / AuditLogEntry
are the SHARED entities defined once in nexusenroll/common/domain.py
and re-exported here so every file in this module can keep writing
`from nexusenroll.admin.data.entities import Course, ...` — the import
path stays local to this module even though the class lives in the
shared kernel. This is what makes the Administrator module part of ONE
integrated system rather than an island: when this module force-enrols
a student or edits a course's capacity, the Student and Faculty
services are reading and writing the very same objects, persisted to
the very same data/*.csv files.

GradeStatus is the one entity that stays local to this module: it
exists purely so Administrator-side reporting code can talk about
"is this grade pending or submitted" without importing the Faculty
module's full GradeState state-machine (which also has richer
Draft/rejection behaviour that only the Faculty service needs).
"""

from enum import Enum

from nexusenroll.common.domain import (  # noqa: F401 (re-exported on purpose)
    AccountStatus,
    Course,
    Program,
    Student,
    Faculty,
    Schedule,
    AuditLogEntry,
)


class GradeStatus(Enum):
    """
    Coarse status of a submitted grade record, as seen from the
    Administrator's side.

    Mirrors the Faculty module's grade-submission workflow
    (Draft -> Pending -> Submitted, see nexusenroll.faculty.service's
    GradeState pattern) so admin-side reporting on grades stays
    consistent with what Faculty produces, without this module needing
    to depend on Faculty's full state-machine implementation.
    """
    PENDING = "PENDING"
    SUBMITTED = "SUBMITTED"
