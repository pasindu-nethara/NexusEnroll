"""
Patterns package.

Role in SOA / 3-Tier Architecture
----------------------------------
Holds the three required design patterns, each isolated in its own
module as requested:

  - factories.py  -> Factory Method (creational)
  - commands.py   -> Command (behavioral)
  - reports.py    -> polymorphic Report classes produced by the
                      Factory Method above (kept alongside factories
                      conceptually, but factories.py imports from here)

These classes sit conceptually "beside" the Service Tier: they are
used BY services and the Facade to construct objects and encapsulate
actions, but they contain no data-access code themselves.
"""
