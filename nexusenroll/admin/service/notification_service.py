"""
nexusenroll/admin/service/notification_service.py

Role: SERVICE TIER — re-exports the shared Notification contract.

The Administrator module's AccountService and OverrideService depend
on NotificationService (Dependency Inversion) to alert a student or
faculty member of an account/enrolment change. That contract, and its
console stand-in implementation, are now defined once in
nexusenroll.common.notifications and shared with the Student and
Faculty modules and the system integration layer — re-exported here so
this module's own files can keep writing
`from nexusenroll.admin.service.notification_service import NotificationService`.
"""

from nexusenroll.common.notifications import (  # noqa: F401 (re-exported on purpose)
    NotificationService,
    ConsoleNotificationService,
)
