"""
service/notification_service.py

Role: SERVICE TIER — Extension point for the system-wide Notification
subsystem (out of scope for this module, per the requirements).

The full NexusEnroll requirements describe a Notification System
that must be "decoupled from core enrolment logic and triggered
automatically" (e.g. notifying a waitlist when a seat opens, or
notifying admins of system errors). Building that subsystem is NOT
part of the Administrator Module. Instead, this file defines the
abstract contract the Admin Module's services call into, so that:

  1. Admin services can be written and tested now against a working
     (but trivial) implementation.
  2. Whoever builds the real, system-wide Notification subsystem
     later can drop in a replacement class implementing the same
     interface (e.g. EmailNotificationService, MessageQueueNotifier)
     with ZERO changes required to any Admin service code — this is
     Dependency Inversion + Open/Closed in practice.

Admin-relevant triggers wired to this interface:
  - force-enrolling a student into a full course (student + advisor
    should be notified),
  - deactivating a student/faculty account,
  - deleting a course that has enrolled students.
"""

from abc import ABC, abstractmethod


class NotificationService(ABC):
    """Abstract contract for sending a notification to a recipient."""

    @abstractmethod
    def notify(self, recipient_id: str, message: str) -> None:
        """Send `message` to `recipient_id`. Implementation is out of scope here."""
        ...


class ConsoleNotificationService(NotificationService):
    """
    Minimal stand-in implementation used only so the Admin Module runs
    standalone. Prints to the console instead of sending a real
    email/push notification. This is NOT the real Notification
    subsystem — it exists purely as a placeholder satisfying the
    interface so force-enrol/deactivate/delete flows have something
    concrete to call during this module's demo.
    """

    def notify(self, recipient_id: str, message: str) -> None:
        print(f"    [notification -> {recipient_id}]: {message}")
