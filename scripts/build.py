#!/usr/bin/env python3
"""Build the publishable artifacts from the YAML records.

Produces, under `dist/`:

  data.json                    every record, for the website
  time-series.tsv              flat exports for people who want a spreadsheet
  expeditions.tsv
  coordination-networks.tsv
  pages/about.html             ABOUT.md rendered as an HTML fragment
  pages/contribute.html        CONTRIBUTING.md rendered as an HTML fragment
  index.html, app.js, style.css   the site, copied from site/

Nothing here is a source of truth. `dist/` is generated on every push and is
not committed.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import markdown
import yaml

REPO = Path(__file__).resolve().parent.parent
DATA = REPO / "data"
SITE = REPO / "site"
DIST = REPO / "dist"

KINDS = ["time-series", "expeditions", "coordination-networks"]

REPO_URL = "https://github.com/merenlab/marine-microbial-observatories"
SITE_URL = "https://microbial-observatories.org"

# Stamped into every generated artifact so the licence travels with the data
# rather than living only in the repository.
LICENCE = {
    "spdx-id": "CC-BY-4.0",
    "name": "Creative Commons Attribution 4.0 International",
    "url": "https://creativecommons.org/licenses/by/4.0/",
    "attribution": f"Marine Microbial Observatories, {SITE_URL}, CC BY 4.0",
    "note": (
        "Applies to this catalogue's own records. Linked publications and archived "
        "datasets carry the licences of their publishers and archives."
    ),
}

# Column order for the flat TSV exports. Multi-valued fields are joined with
# "; " -- these files are a convenience, the YAML remains authoritative.
TSV_COLUMNS = {
    "time-series": [
        "id", "name", "acronym", "status", "countries", "ocean-basins", "sub-region",
        "latitude", "longitude", "sampling-start-year", "sampling-end-year",
        "dna-collection-start-year", "sampling-depth", "sampling-cadence", "omics-types",
        "multiple-sampling-sites", "program-website", "affiliated-institutions",
        "data-accessions", "contact-names", "contact-emails", "publications",
        "checked-by", "checked-on", "notes",
    ],
    "expeditions": [
        "id", "name", "acronym", "program-website", "affiliated-institutions",
        "data-accessions", "sample-metadata-source", "contact-names", "contact-emails",
        "publications", "checked-by", "checked-on", "notes",
    ],
    "coordination-networks": [
        "id", "name", "acronym", "status", "umbrella-organisation", "geographic-scope",
        "established-year", "network-website", "affiliated-institutions",
        "mission-statement", "data-accessions", "contact-names", "contact-emails",
        "publications", "checked-by", "checked-on", "notes",
    ],
}


def load(kind: str) -> list[dict]:
    records = []
    for path in sorted((DATA / kind).glob("*.yml")):
        record = yaml.safe_load(path.read_text(encoding="utf-8"))
        record["_path"] = str(path.relative_to(REPO))
        records.append(record)
    records.sort(key=lambda r: r["name"].lower())
    return records


def flatten(record: dict, column: str):
    """Turn one record field into a single TSV cell."""
    if column == "contact-names":
        value = [c["name"] for c in record.get("contacts", []) if c.get("name")]
    elif column == "contact-emails":
        value = [c["email"] for c in record.get("contacts", []) if c.get("email")]
    elif column in ("checked-by", "checked-on"):
        value = record.get("verification", {}).get(column)
    else:
        value = record.get(column)

    if value is None:
        return ""
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, list):
        return "; ".join(str(v) for v in value)
    return str(value).replace("\t", " ").replace("\n", " ")


def write_tsv(kind: str, records: list[dict]) -> Path:
    path = DIST / f"{kind}.tsv"
    with path.open("w", newline="", encoding="utf-8") as handle:
        # No leading comment line: a header-first TSV is what `pandas.read_csv`
        # and Excel expect. The licence travels via dist/LICENSE and data.json.
        writer = csv.writer(handle, delimiter="\t", lineterminator="\n")
        writer.writerow(TSV_COLUMNS[kind])
        for record in records:
            writer.writerow([flatten(record, c) for c in TSV_COLUMNS[kind]])
    return path


# Markdown documents published as pages on the site. The markdown files are the
# single source for this prose -- it is not duplicated in site/index.html.
PAGES = {
    "about": {"source": "ABOUT.md", "title": "About"},
    "contribute": {"source": "CONTRIBUTING.md", "title": "Contribute"},
}

# Repo-relative links that should point at a page on this site rather than at
# GitHub, so that readers stay on the website.
INTERNAL_LINKS = {
    "ABOUT.md": "#about",
    "CONTRIBUTING.md": "#contribute",
}

# Files the site itself publishes, so links to them stay relative.
SITE_FILES = {
    "time-series.tsv", "expeditions.tsv", "coordination-networks.tsv", "data.json",
}


def rewrite_link(href: str) -> str:
    """Point a link written for GitHub at the right place on the website.

    Markdown in this repository is read in two contexts: on GitHub, where
    relative paths resolve against the repository, and on this site, where they
    do not. Absolute URLs, mail links and pure anchors are left alone; anything
    else is resolved against the repository on GitHub, except for the handful of
    documents and downloads the site publishes itself.
    """
    if href.startswith(("http://", "https://", "mailto:", "#")):
        return href

    path, _, anchor = href.partition("#")
    suffix = f"#{anchor}" if anchor else ""

    # `../../issues/new/choose` is GitHub's relative form for repository routes.
    if path.startswith("../../"):
        return f"{REPO_URL}/{path[6:]}{suffix}"

    if path in INTERNAL_LINKS:
        # An anchor inside another document cannot survive the move to a tab, so
        # link to the tab itself rather than to a heading that is not there yet.
        return INTERNAL_LINKS[path]

    if path in SITE_FILES:
        return f"{path}{suffix}"

    target = REPO / path
    kind = "tree" if target.is_dir() else "blob"
    return f"{REPO_URL}/{kind}/main/{path}{suffix}"


LINK_RE = re.compile(r'(<a\s[^>]*?href=")([^"]+)(")', re.I)

# Regions where text must be left exactly as written: code, and links that are
# already links. Captured so re.split keeps them.
PROTECTED_RE = re.compile(r"(<pre\b.*?</pre>|<code\b.*?</code>|<a\b.*?</a>)", re.S | re.I)
BARE_EMAIL_RE = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]*[A-Za-z]{2,}\b")


def autolink_emails(html: str) -> str:
    """Make email addresses written as plain prose clickable.

    Contact addresses are the whole point of several sections, and markdown
    leaves bare addresses as inert text. Code blocks are skipped so that
    `git clone git@github.com:...` is not turned into a mail link.
    """
    parts = PROTECTED_RE.split(html)
    for index, part in enumerate(parts):
        if index % 2:  # odd indices are the protected regions
            continue
        parts[index] = BARE_EMAIL_RE.sub(
            lambda m: f'<a href="mailto:{m.group(0)}">{m.group(0)}</a>', part
        )
    return "".join(parts)


def render_markdown(path: Path) -> str:
    """Render one markdown file to an HTML fragment with web-correct links."""
    text = path.read_text(encoding="utf-8")

    # The H1 is redundant on the site: the tab already names the page.
    text = re.sub(r"\A#\s+.*\n+", "", text, count=1)

    html = markdown.markdown(
        text,
        extensions=["fenced_code", "tables", "toc", "sane_lists", "attr_list"],
        output_format="html5",
    )
    html = LINK_RE.sub(lambda m: m.group(1) + rewrite_link(m.group(2)) + m.group(3), html)

    # Send outbound links to a new tab, but leave same-page anchors alone.
    def target_blank(match: re.Match) -> str:
        tag = match.group(0)
        href = match.group(2)
        if href.startswith("#") or ' target=' in tag:
            return tag
        return tag[:-1] + ' target="_blank" rel="noopener noreferrer"' + tag[-1:]

    html = re.sub(r'<a\s([^>]*?href="([^"]+)"[^>]*)>', target_blank, html)
    return autolink_emails(html)


def write_pages() -> list[Path]:
    out_dir = DIST / "pages"
    out_dir.mkdir(exist_ok=True)
    written = []
    for slug, page in PAGES.items():
        source = REPO / page["source"]
        if not source.exists():
            print(f"missing page source: {source}", file=sys.stderr)
            raise SystemExit(1)
        target = out_dir / f"{slug}.html"
        target.write_text(render_markdown(source), encoding="utf-8")
        written.append(target)
        print(f"  dist/pages/{slug}.html  (from {page['source']})")
    return written


def git_revision() -> str | None:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=REPO, capture_output=True, text=True, timeout=10, check=True,
        )
        return result.stdout.strip() or None
    except (subprocess.SubprocessError, OSError):
        return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--built-on", default=None,
                        help="ISO date to stamp into data.json (CI passes the run date)")
    args = parser.parse_args()

    DIST.mkdir(exist_ok=True)

    payload: dict = {
        "repository": REPO_URL,
        "licence": LICENCE,
        "revision": git_revision(),
        "built-on": args.built_on,
        "pages": {slug: page["title"] for slug, page in PAGES.items()},
        "counts": {},
        "records": {},
    }

    for kind in KINDS:
        records = load(kind)
        payload["records"][kind] = records
        payload["counts"][kind] = len(records)
        path = write_tsv(kind, records)
        print(f"  {path.relative_to(REPO)}  ({len(records)} rows)")

    (DIST / "data.json").write_text(
        json.dumps(payload, indent=1, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(f"  dist/data.json  ({sum(payload['counts'].values())} records)")

    write_pages()

    for name in ("index.html", "app.js", "style.css"):
        source = SITE / name
        if not source.exists():
            print(f"missing site file: {source}", file=sys.stderr)
            return 1
        shutil.copy2(source, DIST / name)
        print(f"  dist/{name}")

    # Ship the licence next to the downloads, so a copy of dist/ is
    # self-describing without having to visit the repository.
    licence_src = REPO / "LICENSE"
    if licence_src.exists():
        shutil.copy2(licence_src, DIST / "LICENSE")
        print("  dist/LICENSE")

    # Images and other static files referenced by the stylesheet. site/assets/
    # README.md documents the provenance and licence of each one; it is
    # deliberately not published.
    assets_src = SITE / "assets"
    if assets_src.is_dir():
        assets_out = DIST / "assets"
        if assets_out.exists():
            shutil.rmtree(assets_out)
        shutil.copytree(
            assets_src, assets_out,
            ignore=shutil.ignore_patterns("README.md", ".DS_Store"),
        )
        copied = sorted(p.name for p in assets_out.iterdir())
        print(f"  dist/assets/  ({len(copied)}: {', '.join(copied)})")

    # Let the schemas be fetched from the published site, so editors can point
    # at them for autocompletion.
    schema_out = DIST / "schema"
    schema_out.mkdir(exist_ok=True)
    for schema in (REPO / "schema").glob("*.json"):
        shutil.copy2(schema, schema_out / schema.name)
    print(f"  dist/schema/  ({len(list(schema_out.glob('*.json')))} schemas)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
