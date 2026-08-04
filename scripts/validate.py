#!/usr/bin/env python3
"""Validate every YAML record under data/ against its JSON Schema.

Run it before opening a pull request:

    python3 scripts/validate.py

Errors block a pull request. Warnings do not -- they mark records that are
incomplete or suspicious but still publishable, so that a gap in the data never
prevents someone from fixing something else.

Exit codes: 0 clean (warnings allowed), 1 errors found, 2 could not run.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from collections import defaultdict
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover
    print("PyYAML is required: pip install -r requirements.txt", file=sys.stderr)
    sys.exit(2)

try:
    from jsonschema import Draft202012Validator, FormatChecker
except ImportError:  # pragma: no cover
    print("jsonschema is required: pip install -r requirements.txt", file=sys.stderr)
    sys.exit(2)

REPO = Path(__file__).resolve().parent.parent
DATA = REPO / "data"
SCHEMA = REPO / "schema"

KINDS = ["time-series", "expeditions", "coordination-networks"]

# Characters that look like ordinary spaces but are not, plus anything in the
# Unicode "format" category. These survive copy-paste out of spreadsheets and
# silently break links, email addresses and string comparisons.
INVISIBLE = [" ", "​", "‌", "⁠", "﻿"]

ERRORS: list[str] = []
WARNINGS: list[str] = []


def error(where: str, message: str) -> None:
    ERRORS.append(f"{where}: {message}")


def warn(where: str, message: str) -> None:
    WARNINGS.append(f"{where}: {message}")


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(REPO))
    except ValueError:
        return str(path)


# --------------------------------------------------------------------------
# per-file checks
# --------------------------------------------------------------------------

def check_invisible(where: str, node, trail: str = "") -> None:
    if isinstance(node, str):
        found = sorted({f"U+{ord(c):04X}" for c in node if c in INVISIBLE
                        or unicodedata.category(c) == "Cf"})
        if found:
            error(where, f"`{trail}` contains invisible character(s) {', '.join(found)}; "
                         "delete them (they break links and email addresses)")
    elif isinstance(node, dict):
        for key, value in node.items():
            check_invisible(where, value, f"{trail}.{key}" if trail else str(key))
    elif isinstance(node, list):
        for index, value in enumerate(node):
            check_invisible(where, value, f"{trail}[{index}]")


def check_whitespace(where: str, node, trail: str = "") -> None:
    if isinstance(node, str):
        if node != node.strip():
            error(where, f"`{trail}` has leading or trailing whitespace")
        elif re.search(r"  +", node.replace("\n", " ")) and "\n" not in node:
            warn(where, f"`{trail}` contains a run of consecutive spaces")
    elif isinstance(node, dict):
        for key, value in node.items():
            check_whitespace(where, value, f"{trail}.{key}" if trail else str(key))
    elif isinstance(node, list):
        for index, value in enumerate(node):
            check_whitespace(where, value, f"{trail}[{index}]")


def check_record(kind: str, path: Path, record: dict) -> None:
    where = rel(path)

    if record.get("id") != path.stem:
        error(where, f"`id` is `{record.get('id')}` but the filename says `{path.stem}`; "
                     "they must match")

    check_invisible(where, record)
    check_whitespace(where, record)

    # Soft checks: real gaps, but not reasons to block someone else's fix.
    if not record.get("verification", {}).get("checked-on"):
        warn(where, "no `verification.checked-on` date; record has never been confirmed "
                    "against the program by a named person on a known date")

    if not record.get("publications"):
        warn(where, "no `publications` listed")

    # Coordination networks mostly do not hold data themselves, so a missing
    # accession list is normal there and not worth a warning.
    if kind != "coordination-networks" and not record.get("data-accessions"):
        if record.get("data-accessions-note"):
            warn(where, "no `data-accessions`, only a note about them")
        else:
            warn(where, "no `data-accessions`; the molecular data cannot be located from "
                        "this record")

    for index, contact in enumerate(record.get("contacts", [])):
        if "email" not in contact:
            warn(where, f"`contacts[{index}]` ({contact.get('name', '?')}) has no email address")
        if "name" not in contact:
            warn(where, f"`contacts[{index}]` has an email but no name")

    if kind == "time-series":
        if record.get("latitude") is None or record.get("longitude") is None:
            warn(where, "no coordinates, so this program cannot be shown on the map")
        start = record.get("sampling-start-year")
        end = record.get("sampling-end-year")
        if isinstance(start, int) and isinstance(end, int) and end < start:
            error(where, f"`sampling-end-year` ({end}) is before "
                         f"`sampling-start-year` ({start})")
        dna = record.get("dna-collection-start-year")
        if isinstance(start, int) and isinstance(dna, int) and dna < start:
            # A real contradiction, but one that predates this repository, so it
            # is reported rather than blocking unrelated contributions.
            warn(where, f"`dna-collection-start-year` ({dna}) is before the program's "
                        f"`sampling-start-year` ({start}); one of the two is wrong")
        if record.get("multiple-sampling-sites") and not record.get("sampling-sites-note"):
            warn(where, "`multiple-sampling-sites` is true but there is no "
                        "`sampling-sites-note` describing them")
        if record.get("status") == "active" and end != "present":
            warn(where, f"`status` is `active` but `sampling-end-year` is `{end}`")


# --------------------------------------------------------------------------
# cross-record checks
# --------------------------------------------------------------------------

def check_corpus(records: dict[str, list[tuple[Path, dict]]]) -> None:
    seen_ids: dict[str, str] = {}
    for kind, items in records.items():
        for path, record in items:
            rid = record.get("id")
            if not isinstance(rid, str):
                continue
            key = f"{kind}/{rid}"
            if key in seen_ids:
                error(rel(path), f"duplicate id `{rid}` within {kind}")
            seen_ids[key] = rel(path)

    # An acronym reused inside one table makes the website ambiguous.
    for kind, items in records.items():
        by_acronym: dict[str, list[str]] = defaultdict(list)
        for path, record in items:
            acronym = record.get("acronym")
            if acronym:
                by_acronym[acronym.lower()].append(record.get("id", rel(path)))
        for acronym, ids in sorted(by_acronym.items()):
            if len(ids) > 1:
                warn(f"data/{kind}", f"acronym `{acronym}` is used by {len(ids)} records "
                                     f"({', '.join(sorted(ids))})")

    # Identical coordinates across programs: sometimes correct, always worth a look.
    by_coord: dict[tuple, list[str]] = defaultdict(list)
    for path, record in records.get("time-series", []):
        if record.get("latitude") is not None and record.get("longitude") is not None:
            by_coord[(record["latitude"], record["longitude"])].append(record["id"])
    for coord, ids in sorted(by_coord.items()):
        if len(ids) > 1:
            warn("data/time-series",
                 f"{len(ids)} programs share the exact coordinates {coord[0]}, {coord[1]} "
                 f"({', '.join(sorted(ids))}); confirm they are genuinely co-located")


# --------------------------------------------------------------------------

def load_schema(kind: str) -> Draft202012Validator:
    path = SCHEMA / f"{kind}.schema.json"
    schema = json.loads(path.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema, format_checker=FormatChecker())


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--quiet", action="store_true", help="only print errors")
    parser.add_argument("--strict", action="store_true",
                        help="treat warnings as errors (not used in CI)")
    args = parser.parse_args()

    records: dict[str, list[tuple[Path, dict]]] = {}
    total = 0

    for kind in KINDS:
        directory = DATA / kind
        if not directory.is_dir():
            error(f"data/{kind}", "directory is missing")
            continue
        validator = load_schema(kind)
        items: list[tuple[Path, dict]] = []

        stray = sorted(p for p in directory.iterdir()
                       if p.is_file() and p.suffix not in {".yml"})
        for path in stray:
            error(rel(path), "unexpected file; records must be `.yml` (not `.yaml`)")

        for path in sorted(directory.glob("*.yml")):
            total += 1
            try:
                record = yaml.safe_load(path.read_text(encoding="utf-8"))
            except yaml.YAMLError as exc:
                error(rel(path), f"is not valid YAML: {exc}")
                continue
            if not isinstance(record, dict):
                error(rel(path), "must contain a single YAML mapping")
                continue

            for problem in sorted(validator.iter_errors(record), key=lambda e: list(e.path)):
                location = ".".join(str(p) for p in problem.path) or "<root>"
                error(rel(path), f"`{location}` {problem.message}")

            check_record(kind, path, record)
            items.append((path, record))

        records[kind] = items

    check_corpus(records)

    if ERRORS:
        print(f"\n{len(ERRORS)} error(s):\n")
        for line in ERRORS:
            print(f"  ERROR  {line}")
    if WARNINGS and not args.quiet:
        print(f"\n{len(WARNINGS)} warning(s):\n")
        for line in WARNINGS:
            print(f"  warn   {line}")

    counts = ", ".join(f"{k}={len(v)}" for k, v in records.items())
    print(f"\nchecked {total} records ({counts})")
    print(f"{len(ERRORS)} error(s), {len(WARNINGS)} warning(s)")

    if ERRORS:
        return 1
    if args.strict and WARNINGS:
        print("--strict was given and warnings are present", file=sys.stderr)
        return 1
    print("all records valid")
    return 0


if __name__ == "__main__":
    sys.exit(main())
