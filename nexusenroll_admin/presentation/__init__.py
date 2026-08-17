"""
Presentation Tier package.

Role in SOA / 3-Tier Architecture
----------------------------------
CLI-only presentation layer. Contains NO business logic and NO data
access — everything here does is either (a) collect/validate raw
user input syntactically (e.g. "is this a number") and (b) format
data it receives from AdminFacade for display. All real decisions
(is this course ID valid, can this student be force-enrolled, etc.)
happen in the Service Tier via AdminFacade.
"""
