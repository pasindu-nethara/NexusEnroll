"""
nexusenroll/common/csv_utils.py

Role: SHARED DATA TIER — generic CSV read/write + value-encoding
helpers used by every repository in repositories.py.

Domain entities have fields that don't map onto a single CSV cell —
lists (Course.prerequisites, Student.enrolled_course_ids) and dicts
(Student.completed_courses). Rather than each repository re-inventing
its own ad hoc encoding, every repository uses the same two
conventions defined here:
  - a list of strings is stored as one cell, items joined with ";"
    e.g. prerequisites "CS101;CS102"
  - a str -> str dict is stored as one cell of "key:value" pairs
    joined with ";" e.g. completed_courses "CS101:A;CS201:B+"
This keeps the CSV files plain text and human-diffable while still
round-tripping the entities' real shape.
"""

import csv
import os
from typing import Dict, List


def read_rows(path: str) -> List[dict]:
    """Return every row of `path` as a dict (column name -> raw string). Empty list if the file doesn't exist yet."""
    if not os.path.exists(path):
        return []
    with open(path, "r", newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def write_rows(path: str, fieldnames: List[str], rows: List[dict]) -> None:
    """Overwrite `path` with `rows` (list of dicts), creating its parent directory if needed."""
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def append_row(path: str, fieldnames: List[str], row: dict) -> None:
    """Append one row to `path`, writing the header first if the file is new. Used for the append-only audit log."""
    is_new = not os.path.exists(path)
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if is_new:
            writer.writeheader()
        writer.writerow(row)


def encode_list(items: List[str]) -> str:
    return ";".join(items)


def decode_list(cell: str) -> List[str]:
    return [item for item in cell.split(";") if item] if cell else []


def encode_dict(mapping: Dict[str, str]) -> str:
    return ";".join(f"{k}:{v}" for k, v in mapping.items())


def decode_dict(cell: str) -> Dict[str, str]:
    if not cell:
        return {}
    result: Dict[str, str] = {}
    for pair in cell.split(";"):
        if not pair:
            continue
        key, _, value = pair.partition(":")
        result[key] = value
    return result
