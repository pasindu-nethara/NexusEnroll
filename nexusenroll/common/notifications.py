"""
nexusenroll/common/notifications.py

Role: SHARED SERVICE TIER — the system-wide Notification subsystem
required by section 4 of the requirements ("the system must have a
notification mechanism ... automated and decoupled from the core
enrolment logic").

NotificationService is an abstract contract (Dependency Inversion):
every module that needs to notify someone (Student module dropping a
waitlisted seat, Administrator deactivating an account or
force-enrolling a student, Faculty module alerting an advisor) depends
only on THIS interface, never on a concrete delivery mechanism. Today
the only implementation is ConsoleNotificationService, which just
prints — swapping in EmailNotificationService or
PushNotificationService later requires zero changes to any calling
code (Open/Closed Principle).
"""

from abc import ABC, abstractmethod


class NotificationService(ABC):
    """Abstract contract for sending a notification to a recipient."""

    @abstractmethod
    def notify(self, recipient_id: str, message: str) -> None:
        """Send `message` to `recipient_id`. Delivery mechanism is out of scope here."""
        ...


class ConsoleNotificationService(NotificationService):
    """
    Minimal stand-in implementation used so the proof-of-concept runs
    without any real email/SMS/push infrastructure. Prints to the
    console instead. This is NOT the real production Notification
    subsystem — it exists purely as a placeholder satisfying the
    interface so every notify()-triggering flow in the demo has
    something concrete to call.
    """

    def notify(self, recipient_id: str, message: str) -> None:
        print(f"    [notification -> {recipient_id}]: {message}")
