"""
Service Tier package.

Role in SOA / 3-Tier Architecture
----------------------------------
This package is the Business/Service Tier: application logic,
orchestration and validation. Services here:
  - depend only on repository ABSTRACTIONS from data/repositories.py
    (never on the in-memory implementations directly) — Dependency
    Inversion Principle,
  - depend only on an abstract NotificationService (see
    notification_service.py) so the real system-wide Notification
    subsystem can be plugged in later without touching this code,
  - are the ONLY layer that enforces business rules (e.g. "you
    cannot delete a course that still has enrolled students") — the
    Presentation Tier never contains business logic, and the Data
    Tier never validates anything.
Each service class has one clear responsibility (Course, Program,
Account, Override, Reporting) — Single Responsibility Principle.
"""
