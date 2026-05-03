"""Sync trust-zone rules from a live IriusRisk REST API into a per-installation
mapping override.

Companion to ``regen_iriusrisk_defaults.py``: the default ``iriusrisk.yaml``
ships only the 6 standard IriusRisk trust zones (Internet, Public, Public
Cloud, Trusted Partner, Private Secured, Third Party / SaaS). Many
installations add custom zones (regulatory, geographic, organisational).
This script pulls them via the REST API and produces a *local* mapping
override that includes a name-patterned zone rule per fetched zone.

The bundled ``iriusrisk.yaml`` is NEVER overwritten — output goes to a
``*.local.yaml`` path (auto-gitignored) which the user passes via
``archithreat convert ... --mapping <path>``.

Authentication: ``IRIUSRISK_BASE_URL`` + ``IRIUSRISK_TOKEN`` env vars,
or ``--cache <path>`` to reuse a previous dump (offline mode).

Usage:
    # Print the zone_rules YAML block to stdout (review before applying):
    IRIUSRISK_BASE_URL=https://example.iriusrisk.com \\
    IRIUSRISK_TOKEN=<token> \\
    python scripts/sync_iriusrisk_zones.py --print

    # Generate a full mapping override file:
    IRIUSRISK_BASE_URL=https://example.iriusrisk.com \\
    IRIUSRISK_TOKEN=<token> \\
    python scripts/sync_iriusrisk_zones.py --apply mapping.local.yaml

    # Then:
    archithreat convert model.xml model.drawio \\
        --target iriusrisk --mapping mapping.local.yaml

The cache file (``scripts/.iriusrisk-trust-zones.json``) is gitignored —
it can carry installation-private trust-zone data.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_YAML = REPO_ROOT / "src" / "archithreat" / "core" / "defaults" / "iriusrisk.yaml"
DEFAULT_CACHE = REPO_ROOT / "scripts" / ".iriusrisk-trust-zones.json"

# Standard IriusRisk trust-zone styling. Only ir.ref differs per zone.
ZONE_STYLE_TEMPLATE = (
    "ir.ref={ref};rounded=1;whiteSpace=wrap;recursiveResize=0;html=1;"
    "verticalAlign=top;align=left;dashed=1;strokeWidth=1;arcSize=3;"
    "absoluteArcSize=1;spacingTop=1;spacingLeft=32;strokeColor=#7575EB;"
    "fillColor=#F0F0FF;fillOpacity=30;fontColor=#5651E0;connectable=0;"
    "container=1;source=iriusrisk;ir.type=TRUSTZONE;"
)

# Marks the start and end of zone_rules in iriusrisk.yaml. The script
# replaces everything between (exclusive) when --apply is used.
ZONE_RULES_HEADER = re.compile(r"^zone_rules:\s*$", re.MULTILINE)
SYNTHETIC_HEADER = re.compile(r"^synthetic_zones:\s*$", re.MULTILINE)


def fetch_zones(base_url: str, token: str) -> list[dict]:
    items: list[dict] = []
    page = 0
    size = 50
    while True:
        url = f"{base_url.rstrip('/')}/api/v2/trust-zones?page={page}&size={size}"
        for attempt in range(8):
            try:
                req = urllib.request.Request(
                    url,
                    headers={
                        "api-token": token,
                        "Accept": "application/hal+json",
                        "User-Agent": "archithreat-zones-sync/1.0",
                    },
                )
                with urllib.request.urlopen(req, timeout=30) as resp:
                    data = json.load(resp)
                break
            except urllib.error.HTTPError as exc:
                if exc.code in (403, 429, 502, 503):
                    wait = min(60, 3 * (attempt + 1))
                    print(f"  HTTP {exc.code} — retry in {wait}s", file=sys.stderr)
                    time.sleep(wait)
                else:
                    raise
        else:
            raise RuntimeError(f"failed after retries: {url}")
        page_items = data.get("_embedded", {}).get("items", [])
        items.extend(page_items)
        meta = data["page"]
        if meta["number"] + 1 >= meta["totalPages"]:
            break
        page += 1
        time.sleep(0.3)
    return items


def load_or_fetch(cache: Path, force_refresh: bool) -> list[dict]:
    if cache.exists() and not force_refresh:
        return json.loads(cache.read_text())
    base = os.environ.get("IRIUSRISK_BASE_URL")
    token = os.environ.get("IRIUSRISK_TOKEN")
    if not base or not token:
        raise SystemExit(
            "no cache and IRIUSRISK_BASE_URL / IRIUSRISK_TOKEN not set; "
            "either set them or pass --cache <path>"
        )
    items = fetch_zones(base, token)
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps(items))
    print(f"cached {len(items)} trust zones → {cache}", file=sys.stderr)
    return items


def name_pattern_for(zone_name: str) -> str:
    """Build a case-insensitive whole-word match for a zone name.

    Special regex characters in the name are escaped so a name like
    ``Third Party / SaaS`` doesn't blow up the parser.
    """
    return rf"(?i)^{re.escape(zone_name)}$"


def build_zone_rules(zones: list[dict]) -> str:
    """Render the YAML ``zone_rules:`` block. One rule pair per zone
    (Grouping + Location), matched by exact name, with the zone's
    ``ir.ref`` UUID embedded in the style.
    """
    out: list[str] = ["zone_rules:"]
    for z in zones:
        name = z.get("name", "")
        ref = z.get("id", "")
        if not name or not ref:
            continue
        pattern = name_pattern_for(name)
        style = ZONE_STYLE_TEMPLATE.format(ref=ref)
        out.append(f"  # {name} (referenceId: {z.get('referenceId', '')!r}, trustRating: {z.get('trustRating', '')})")
        for archimate_type in ("Grouping", "Location"):
            out.append("  - match:")
            out.append(f"      archimate_type: {archimate_type}")
            out.append(f"      name_pattern: '{pattern}'")
            out.append("    iriusrisk:")
            out.append("      zone_name_property: name")
            out.append(f'      style: "{style}"')
    out.append("")
    return "\n".join(out)


def replace_zone_rules(yaml_text: str, new_zone_rules: str) -> str:
    start_match = ZONE_RULES_HEADER.search(yaml_text)
    if not start_match:
        raise RuntimeError("could not find `zone_rules:` header in mapping YAML")
    end_match = SYNTHETIC_HEADER.search(yaml_text, start_match.end())
    if not end_match:
        raise RuntimeError("could not find `synthetic_zones:` header (zone_rules end marker)")
    return yaml_text[: start_match.start()] + new_zone_rules + "\n" + yaml_text[end_match.start() :]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--cache",
        type=Path,
        default=DEFAULT_CACHE,
        help="JSON cache file. Defaults to scripts/.iriusrisk-trust-zones.json (gitignored).",
    )
    ap.add_argument("--refresh", action="store_true", help="Refetch from API.")
    grp = ap.add_mutually_exclusive_group(required=True)
    grp.add_argument(
        "--print",
        dest="print_only",
        action="store_true",
        help="Print the zone_rules YAML block to stdout. Review before applying.",
    )
    grp.add_argument(
        "--apply",
        type=Path,
        metavar="OUTPUT.local.yaml",
        help=(
            "Clone the bundled iriusrisk.yaml into OUTPUT, replacing its "
            "zone_rules with API-derived ones. OUTPUT must end in `.local.yaml` "
            "so it's gitignored."
        ),
    )
    args = ap.parse_args()

    if args.apply and not args.apply.name.endswith(".local.yaml"):
        raise SystemExit(
            f"--apply path must end in .local.yaml (got {args.apply.name!r}); "
            "this guarantees the file is gitignored and tenant trust-zone data "
            "is never accidentally committed."
        )

    zones = load_or_fetch(args.cache, args.refresh)
    print(f"library: {len(zones)} trust zones", file=sys.stderr)

    block = build_zone_rules(zones)

    if args.print_only:
        print(block)
        return

    yaml_text = DEFAULT_YAML.read_text()
    new_text = replace_zone_rules(yaml_text, block)
    args.apply.parent.mkdir(parents=True, exist_ok=True)
    args.apply.write_text(new_text)
    print(f"\nwrote {args.apply}", file=sys.stderr)
    print(
        f"\nUse it via:\n  archithreat convert model.xml out.drawio "
        f"--target iriusrisk --mapping {args.apply}",
        file=sys.stderr,
    )


if __name__ == "__main__":
    main()
