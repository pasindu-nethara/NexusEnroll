"""
Data Tier package.

Role in SOA / 3-Tier Architecture
----------------------------------
This package IS the Data Tier of the Administrator Module's 3-tier
architecture:

    Presentation Tier (CLI)  -->  Service Tier (business logic)  -->  Data Tier (this package)

Nothing outside this package should know HOW data is stored. Every
repository exposes only an abstract interface (an ABC). The current
implementation stores data in plain Python dictionaries/lists in
memory, but because callers only depend on the abstract interfaces
(see repositories.py), a future team member could swap in a real
database-backed repository (e.g. PostgresCourseRepository) without
changing a single line in the Service Tier or Presentation Tier.
This is the Dependency Inversion Principle (the 'D' in SOLID) in
action: high-level modules (services) depend on abstractions
(repository interfaces), not on low-level concrete storage details.
"""
