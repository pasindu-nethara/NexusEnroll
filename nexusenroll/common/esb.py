"""
nexusenroll/common/esb.py

Role: SHARED ARCHITECTURAL BACKBONE — Enterprise Service Bus (ESB).

ARCHITECTURAL PATTERN: Service-Oriented Architecture (SOA)
------------------------------------------------------------
NexusEnroll is decomposed into coarse-grained, independently reasoned
about SERVICES — StudentService, FacultyService, AdministratorService
(AdminFacade) and a NotificationService — each exposing a formal
CONTRACT (an abstract interface) as its only entry point. Services
never call each other's internals directly; instead they communicate
by publishing/subscribing to named events on this shared bus. This is
what lets the university plug in a brand new service later (the
assignment's example: a Financial Aid System) by having it simply
subscribe to the events it cares about (e.g. "grades_submitted",
"student_deactivated") — none of the three existing modules need to
change.

This differs from:
  - Microservices: fine-grained, each with its own datastore and
    independent scaling. Overkill for a single university's three
    coarse business domains.
  - 3-Tier: layers within a single deployable application, not
    separately-reasoned-about services with their own contracts.
    (NexusEnroll actually uses 3-Tier *within* each service — see each
    module's data/service/presentation split — SOA at the system
    level, 3-Tier inside each service, is the "one or a combination"
    hybrid the assignment explicitly allows.)

This module is a lightweight IN-PROCESS simulation of the bus so the
proof-of-concept is runnable without external infrastructure. A real
deployment would swap EnterpriseServiceBus for an actual product
(e.g. RabbitMQ, Kafka, MuleESB, or an API gateway + message queue).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Dict, List


class ServiceMessage:
    """
    A single message/event travelling on the bus. In a real SOA
    deployment this would typically be a SOAP/XML or JSON envelope
    with routing headers; here it is kept minimal for the PoC.
    """

    def __init__(self, event_type: str, source_service: str, payload: dict):
        self.event_type = event_type
        self.source_service = source_service
        self.payload = payload
        self.timestamp = datetime.now()


class ServiceEndpoint(ABC):
    """
    Contract every service that listens on the bus must implement.
    This is the ESB-side analogue of the OBSERVER pattern's Observer
    role: the bus doesn't know what each service does with a message,
    only that it can receive one (Interface Segregation: this is the
    *only* thing a bus subscriber must be able to do).
    """

    @abstractmethod
    def receive(self, message: ServiceMessage) -> None: ...


class EnterpriseServiceBus:
    """
    Simulates the ESB: services publish messages to named channels
    (event types) and other services subscribe to those channels. This
    is the mechanism that lets NexusEnroll plug a new service in (e.g.
    a future Financial Aid System) without changing the Student,
    Faculty, or Administrator service — the new service just
    subscribes to the events it cares about.

    Internally this is an application of the OBSERVER pattern: the bus
    is the Subject, ServiceEndpoint.receive() is Observer.update(), and
    publish() is notify() scoped to one event_type "topic" instead of
    broadcasting to every observer.
    """

    def __init__(self) -> None:
        self._subscribers: Dict[str, List[ServiceEndpoint]] = {}

    def subscribe(self, event_type: str, endpoint: ServiceEndpoint) -> None:
        self._subscribers.setdefault(event_type, []).append(endpoint)

    def publish(self, message: ServiceMessage) -> None:
        for endpoint in self._subscribers.get(message.event_type, []):
            endpoint.receive(message)
