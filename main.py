"""
main.py — NexusEnroll's single entry point.

Run with:  python main.py

This is a deliberately thin launcher: it exists so the command to run
the whole system is exactly `python main.py` from the repository root,
the same way any real deployable application has one obvious start
command. All actual composition (wiring the shared, CSV-backed
repositories and the three service modules together) lives in
nexusenroll/system/app.py — see that file for the composition root.
"""

from nexusenroll.system.app import main

if __name__ == "__main__":
    main()
