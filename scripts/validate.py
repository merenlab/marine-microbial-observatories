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
import textwrap
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

# Findings are collected as (category, explanation, file, detail) and printed
# grouped by category, not one line per record. The same gap in forty records is
# one thing to understand and forty files to open, so it reads as one heading
# with forty paths under it. `detail` carries whatever is specific to a record
# and is left empty when the heading already says everything.
ERRORS: list[tuple[str, str, str, str]] = []
WARNINGS: list[tuple[str, str, str, str]] = []


def error(category: str, explain: str, where: str, detail: str = "") -> None:
    ERRORS.append((category, explain, where, detail))


def warn(category: str, explain: str, where: str, detail: str = "") -> None:
    WARNINGS.append((category, explain, where, detail))


RULE = 74


def render(findings: list[tuple[str, str, str, str]], label: str) -> None:
    """Print findings grouped under one heading per category."""
    groups: dict[str, tuple[str, list[tuple[str, str]]]] = {}
    for category, explain, where, detail in findings:
        groups.setdefault(category, (explain, []))[1].append((where, detail))

    # Widest problem first: what affects forty records is usually worth reading
    # before what affects one. Ties break by name so runs stay comparable.
    for category, (explain, items) in sorted(groups.items(),
                                             key=lambda kv: (-len(kv[1][1]), kv[0])):
        # "records" only when the list really is one line per record file. The
        # corpus-level checks report against a directory and can name it twice,
        # so those count findings instead and the heading stays true either way.
        listed = sorted(set(items))
        paths = {where for where, _ in listed}
        noun = ("record" if len(paths) == len(listed) and all(p.endswith(".yml") for p in paths)
                else "finding")
        heading = f"{label}: {category}  ({len(listed)} {noun}{'' if len(listed) == 1 else 's'})"
        print(f"\n{heading}")
        print("-" * RULE)
        print(f"{textwrap.fill(explain, RULE)}\n")
        for where, detail in listed:
            print(f"- {where}" + (f" — {detail}" if detail else ""))


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
            error("Invisible characters",
                  "These survive copy-paste out of spreadsheets and silently break links, "
                  "email addresses and string comparisons. Delete them:",
                  where, f"`{trail}` contains {', '.join(found)}")
    elif isinstance(node, dict):
        for key, value in node.items():
            check_invisible(where, value, f"{trail}.{key}" if trail else str(key))
    elif isinstance(node, list):
        for index, value in enumerate(node):
            check_invisible(where, value, f"{trail}[{index}]")


def check_whitespace(where: str, node, trail: str = "") -> None:
    if isinstance(node, str):
        if node != node.strip():
            error("Leading or trailing whitespace",
                  "Strip the whitespace surrounding these values:",
                  where, f"`{trail}`")
        elif re.search(r"  +", node.replace("\n", " ")) and "\n" not in node:
            warn("Consecutive spaces",
                 "Almost always a typo; collapse each run to a single space:",
                 where, f"`{trail}`")
    elif isinstance(node, dict):
        for key, value in node.items():
            check_whitespace(where, value, f"{trail}.{key}" if trail else str(key))
    elif isinstance(node, list):
        for index, value in enumerate(node):
            check_whitespace(where, value, f"{trail}[{index}]")


def check_record(kind: str, path: Path, record: dict) -> None:
    where = rel(path)

    if record.get("id") != path.stem:
        error("Filename and `id` disagree",
              "A filename is a record's permanent address, so `id` has to match it:",
              where, f"`id` is `{record.get('id')}` but the filename says `{path.stem}`")

    check_invisible(where, record)
    check_whitespace(where, record)

    # Soft checks: real gaps, but not reasons to block someone else's fix.
    if not record.get("verification", {}).get("checked-on"):
        warn("Missing `verification.checked-on`",
             "These records have never been confirmed against the program by a named "
             "person on a known date, so there is no way to tell how stale they are:",
             where)

    if not record.get("publications"):
        warn("Missing `publications`",
             "No publication was linked to these records:",
             where)

    # Coordination networks mostly do not hold data themselves, so a missing
    # accession list is normal there and not worth a warning.
    if kind != "coordination-networks" and not record.get("data-accessions"):
        if record.get("data-accessions-note"):
            warn("`data-accessions` given only as prose",
                 "These records describe where their data lives but list no accession, "
                 "so nothing can link to an archive:",
                 where)
        else:
            warn("Missing `data-accessions`",
                 "Molecular data cannot be located from these records:",
                 where)

    for index, contact in enumerate(record.get("contacts", [])):
        if "email" not in contact:
            warn("Contact without an email address",
                 "These people are named but cannot be written to:",
                 where, f"`contacts[{index}]` ({contact.get('name', '?')})")
        if "name" not in contact:
            warn("Contact without a name",
                 "These records give an address but no person to ask for:",
                 where, f"`contacts[{index}]`")

    if kind == "expeditions":
        samples = record.get("samples") or []
        if not samples:
            warn("Missing `samples`",
                 "Expeditions have no single coordinate of their own, so without a sample "
                 "list these contribute nothing to the map:",
                 where)
        # An accession appearing twice means the same sample was ingested from two
        # study codes, which would double-plot it and inflate the count.
        seen_accessions: dict[str, int] = {}
        unplaced = []
        for index, sample in enumerate(samples):
            accession = sample.get("accession")
            if accession in seen_accessions:
                error("Repeated sample accession",
                      "The same sample is listed twice, which double-plots it on the map "
                      "and inflates the count:",
                      where, f"`samples[{index}]` repeats `{accession}` from "
                             f"`samples[{seen_accessions[accession]}]`")
            else:
                seen_accessions[accession] = index
            if sample.get("latitude") is None or sample.get("longitude") is None:
                unplaced.append(accession)
        # Listed but unplaceable: the sample is part of the expedition and belongs
        # in the record, it just cannot be drawn until someone fills the gap in.
        if unplaced:
            shown = ", ".join(unplaced[:5]) + (f", and {len(unplaced) - 5} more"
                                               if len(unplaced) > 5 else "")
            warn("Samples without coordinates",
                 "These samples belong to the expedition but cannot be drawn until "
                 "someone fills their coordinates in:",
                 where, f"{len(unplaced)} of {len(samples)} samples ({shown})")

    if kind == "time-series":
        if record.get("latitude") is None or record.get("longitude") is None:
            warn("Missing coordinates",
                 "These programs cannot be shown on the map:",
                 where)
        start = record.get("sampling-start-year")
        end = record.get("sampling-end-year")
        if isinstance(start, int) and isinstance(end, int) and end < start:
            error("Sampling ends before it starts",
                  "`sampling-end-year` precedes `sampling-start-year`:",
                  where, f"{end} is before {start}")
        dna = record.get("dna-collection-start-year")
        if isinstance(start, int) and isinstance(dna, int) and dna < start:
            # A real contradiction, but one that predates this repository, so it
            # is reported rather than blocking unrelated contributions.
            warn("DNA collected before sampling began",
                 "`dna-collection-start-year` precedes `sampling-start-year`; one of "
                 "the two years is wrong:",
                 where, f"DNA from {dna}, program from {start}")
        if record.get("multiple-sampling-sites") and not record.get("sampling-sites-note"):
            warn("Multiple sites, no `sampling-sites-note`",
                 "These programs sample more than one site but do not describe the layout:",
                 where)
        if record.get("status") == "active" and end != "present":
            warn("Active status, but sampling has an end year",
                 "An active program should carry `sampling-end-year: present`:",
                 where, f"`sampling-end-year` is `{end}`")


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
                error("Duplicate record `id`",
                      "Two records in the same category claim the same id:",
                      rel(path), f"`{rid}` is also used by {seen_ids[key]}")
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
                warn("Acronym used by more than one record",
                     "A reused acronym makes the website ambiguous:",
                     f"data/{kind}", f"`{acronym}` is used by {', '.join(sorted(ids))}")

    # Identical coordinates across programs: sometimes correct, always worth a look.
    by_coord: dict[tuple, list[str]] = defaultdict(list)
    for path, record in records.get("time-series", []):
        if record.get("latitude") is not None and record.get("longitude") is not None:
            by_coord[(record["latitude"], record["longitude"])].append(record["id"])
    for coord, ids in sorted(by_coord.items()):
        if len(ids) > 1:
            warn("Programs sharing exact coordinates",
                 "These share a single marker on the map. Sometimes correct, always "
                 "worth confirming they are genuinely co-located:",
                 "data/time-series",
                 f"{coord[0]}, {coord[1]} shared by {', '.join(sorted(ids))}")


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
            error("Missing record directory",
                  "These directories should hold one `.yml` per record but do not exist:",
                  f"data/{kind}")
            continue
        validator = load_schema(kind)
        items: list[tuple[Path, dict]] = []

        stray = sorted(p for p in directory.iterdir()
                       if p.is_file() and p.suffix not in {".yml"})
        for path in stray:
            error("Unexpected file in a record directory",
                  "Records must be `.yml` (not `.yaml`), and nothing else belongs here:",
                  rel(path))

        for path in sorted(directory.glob("*.yml")):
            total += 1
            try:
                record = yaml.safe_load(path.read_text(encoding="utf-8"))
            except yaml.YAMLError as exc:
                error("Not valid YAML",
                      "These files could not be parsed at all:",
                      rel(path), str(exc).replace("\n", " "))
                continue
            if not isinstance(record, dict):
                error("Not a single YAML mapping",
                      "Each record file must contain exactly one mapping of fields:",
                      rel(path))
                continue

            for problem in sorted(validator.iter_errors(record), key=lambda e: list(e.path)):
                location = ".".join(str(p) for p in problem.path) or "<root>"
                error(f"Does not match {kind}.schema.json",
                      f"Every field is defined in schema/{kind}.schema.json; these do "
                      f"not fit their definition:",
                      rel(path), f"`{location}` {problem.message}")

            check_record(kind, path, record)
            items.append((path, record))

        records[kind] = items

    check_corpus(records)

    if ERRORS:
        print()
        print("=" * RULE)
        print(f"{len(ERRORS)} error(s) — these block a pull request")
        print("=" * RULE)
        render(ERRORS, "Error")
    if WARNINGS and not args.quiet:
        print()
        print("=" * RULE)
        print(textwrap.fill(
            f"{len(WARNINGS)} warning(s) — these do not block a pull request, but fixing "
            "them is one of the best ways to improve the catalogue", RULE))
        print("=" * RULE)
        render(WARNINGS, "Warning")

    counts = ", ".join(f"{k}={len(v)}" for k, v in records.items())
    print(f"\n{'-' * RULE}")
    print(f"checked {total} records ({counts})")
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
