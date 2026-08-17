# NexusEnroll

A university course-enrolment system for **SCS 2303 — Software Architecture, Assignment 3**.
NexusEnroll models Student, Faculty, and Administrator functionality as three services on a
shared Enterprise Service Bus (Service-Oriented Architecture at the system level, 3-Tier inside
each service), backed by a single set of CSV data files.

## Running it

Requires Python 3.10+, standard library only — no external dependencies.

```bash
python main.py
```

Log in as **Student**, **Faculty**, or **Administrator** as many times as you like in one run;
all three see the same live system state. Sample logins seeded in `data/`:

- Students: `S001` (Kasun), `S002` (Amaya), `S003` (Tharindu), `S004` (Nimal)
- Faculty: `F001` (Dr. Perera, CS), `F002` (Dr. Silva, Business), `F003` (Dr. Jayasuriya, Math)

Every change (enrolments, grades, overrides, account edits, the audit log) is written back to
the CSV files under `data/` as you go, so state persists between runs.

## Project layout

```
NexusEnroll/
├── main.py                    # single entry point — python main.py
├── data/                      # CSV-backed data store (the system's persistence layer)
│   ├── courses.csv
│   ├── programs.csv
│   ├── students.csv
│   ├── faculty.csv
│   └── audit_log.csv
├── nexusenroll/                # all source code, one importable package
│   ├── common/                 # shared kernel: domain entities, CSV repositories, ESB, notifications
│   ├── student/                # Student service (catalogue, enrolment, schedule, progress)
│   ├── faculty/                # Faculty service (roster, grading, course-change requests)
│   ├── admin/                  # Administrator service (3-Tier internally: data/service/patterns/presentation)
│   └── system/                 # integration layer: wires the three services + ESB subscribers + CLI menu
└── SA-Assignment-3-2026.pdf
```

## Architecture and design patterns

See the in-code documentation — every module's file starts with a docstring explaining its
role, the patterns it applies, and why. Start at `nexusenroll/common/esb.py` for the
architectural rationale, and `nexusenroll/system/app.py` for how the three services are
composed.

Patterns used: Singleton, Factory Method (×3 hierarchies), Strategy (×2), Chain of
Responsibility, Observer, State, Command (×2), Facade (×2).
