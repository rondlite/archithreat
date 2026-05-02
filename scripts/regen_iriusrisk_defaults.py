"""Regenerate src/archithreat/core/defaults/iriusrisk.yaml against a live
IriusRisk REST API library.

The bundled YAML's component refs drift over time as IriusRisk publishes new
shape libraries (and as installations switch between Community and CD-V2-*
namespaces). This script:

  1. Pulls the full component-definition catalog from /api/v2/components.
  2. Caches the raw response to a JSON file so reruns don't need the API.
  3. Reads the existing iriusrisk.yaml, finds every
     ``ir.componentDefinition.ref=<x>`` and matching ``component_type: <x>``
     occurrence, and rewrites both to the closest CD-V2-* equivalent in
     the live library.
  4. Reports unmapped refs so the modeler can fill them in.

Authentication: set ``IRIUSRISK_BASE_URL`` and ``IRIUSRISK_TOKEN`` env vars,
or pass --cache to skip the API call and reuse a previous dump.

Usage:
    IRIUSRISK_BASE_URL=https://example.iriusrisk.com \\
    IRIUSRISK_TOKEN=<token> \\
    python scripts/regen_iriusrisk_defaults.py

    # Or, offline against a cached dump:
    python scripts/regen_iriusrisk_defaults.py --cache /tmp/components.json

The cache file is gitignored — it can carry installation-private data.
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
YAML_PATH = REPO_ROOT / "src" / "archithreat" / "core" / "defaults" / "iriusrisk.yaml"
DEFAULT_CACHE = REPO_ROOT / "scripts" / ".iriusrisk-components.json"

REF_PATTERN = re.compile(r"ir\.componentDefinition\.ref=([A-Za-z0-9_\-]+)")
TYPE_PATTERN = re.compile(r"^(\s*component_type:\s*)([A-Za-z0-9_\-]+)\s*$")

# Manual overrides for refs whose CD-V2 name differs from a mechanical
# uppercase + prefix transform. Built by inspecting the live library
# (see scripts/iriusrisk-library-audit.md if/when documented).
MANUAL_OVERRIDES: dict[str, str] = {
    "CD-AWS-IAM": "CD-V2-AWS-IAM-IDENTITY-AND-ACCESS-MANAGEMENT",
    "CD-CMS": "CD-V2-CMS-CONTENT-MANAGEMENT-SYSTEM",
    "CD-CONTENT-DELIVERY-NETWORK": "CD-V2-CDN-CONTENT-DELIVERY-NETWORK",
    "CD-CUSTOMER-RELATIONSHIP-MANAGEMENT": "CD-V2-CRM-CUSTOMER-RELATIONSHIP-MANAGEMENT",
    "CD-DLP": "CD-V2-DLP-DATA-LOSS-PREVENTION",
    "CD-DNS": "CD-V2-DNS-DOMAIN-NAME-SYSTEM",
    "CD-EDR": "CD-V2-EDR-ENDPOINT-DETECTION-AND-RESPONSE",
    "CD-ELASTICACHE-FOR-REDIS": "CD-V2-AWS-ELASTICACHE-FOR-REDIS",
    "CD-ENTERPRISE-RESOURCE-PLANNING": "CD-V2-ERP-ENTERPRISE-RESOURCE-PLANNING",
    "CD-GOOGLE-CLOUD-COMPUTE-ENGINE": "CD-V2-GCP-COMPUTE-ENGINE",
    "CD-GOOGLE-CLOUD-FUNCTIONS": "CD-V2-GCP-FUNCTIONS",
    "CD-GOOGLE-CLOUD-IAM": "CD-V2-GCP-IAM-IDENTITY-AND-ACCESS-MANAGEMENT",
    "CD-GOOGLE-CLOUD-MEMORYSTORE-REDIS": "CD-V2-GCP-MEMORYSTORE-FOR-REDIS",
    "CD-GOOGLE-CLOUD-PUB-SUB": "CD-V2-GCP-PUB-SUB",
    "CD-INTRUSION-DETECTION-SYSTEM": "CD-V2-IDS-INTRUSION-DETECTION-SYSTEM",
    "CD-INTRUSION-PREVENTION-SYSTEM": "CD-V2-IPS-INTRUSION-PREVENTION-SYSTEM",
    "CD-ISP": "CD-V2-ISP-INTERNET-SERVICE-PROVIDER",
    "CD-KERBEROS-AS": "CD-V2-KERBEROS-AUTHENTICATION-SERVER",
    "CD-MICROSOFT-AZURE-BLOB-STORAGE": "CD-V2-AZURE-BLOB-STORAGE",
    "CD-MICROSOFT-AZURE-CACHE-REDIS": "CD-V2-AZURE-CACHE-FOR-REDIS",
    "CD-MICROSOFT-AZURE-VM-SCALE-SET": "CD-V2-AZURE-VIRTUAL-MACHINE-SCALE-SETS",
    "CD-MICROSOFT-IIS": "CD-V2-MICROSOFT-IIS-SERVER",
    "CD-MSK": "CD-V2-AWS-MSK-MANAGED-STREAMING-FOR-APACHE-KAFKA",
    "CD-NGINX": "CD-V2-NGINX-SERVER",
    "CD-PAYMENT-GW": "CD-V2-PAYMENT-GATEWAY",
    "CD-SIEM": "CD-V2-SIEM-SECURITY-INFORMATION-AND-EVENT-MANAGEMENT",
    "CD-VPN": "CD-V2-AWS-CLIENT-VPN",
    "CD-XDR": "CD-V2-XDR-EXTENDED-DETECTION-AND-RESPONSE",
    "api-gateway-microservice": "CD-V2-API-GATEWAY",
    "aws-lambda-function": "CD-V2-AWS-LAMBDA",
    "cf-cloudfront": "CD-V2-AWS-CLOUDFRONT",
    "cloudwatch": "CD-V2-AWS-CLOUDWATCH",
    "cognito": "CD-V2-AWS-COGNITO",
    "dynamodb": "CD-V2-AWS-DYNAMODB",
    "ec2": "CD-V2-AWS-EC2",
    "elastic-container-kubernetes": "CD-V2-AWS-EKS-ELASTIC-KUBERNETES-SERVICE",
    # Lemonade-only refs already handled by the surgical first pass; keep here
    # so the regen is idempotent.
    "web-ui": "CD-V2-WEB-UI",
    "web-service": "CD-V2-WEB-SERVICE",
    "postgresql": "CD-V2-POSTGRESQL",
    "mobile-device-client": "CD-V2-MOBILE-DEVICE-CLIENT",
    "CD-BROWSER": "CD-V2-BROWSER",
    "other-database": "CD-V2-OTHER-DATABASE",
    # Cloud-vendor refs whose canonical lowercase form has no CD-V2- mirror.
    "elastic-container-service": "CD-V2-AWS-ECS",
    "fargate": "CD-V2-AWS-FARGATE",
    "google-bigquery": "CD-V2-GCP-BIGQUERY",
    "google-kubernetes": "CD-V2-GCP-KUBERNETES",
    "kinesis-data-streams": "CD-V2-AWS-KINESIS-DATA-STREAMS",
    "microsoft-azure-active-directory": "CD-V2-MICROSOFT-ENTRA-ID",
    "microsoft-azure-cosmos-db": "CD-V2-AZURE-COSMOS-DB",
    "microsoft-azure-functions": "CD-V2-AZURE-FUNCTIONS",
    "microsoft-azure-key-vault": "CD-V2-AZURE-KEY-VAULT",
    "microsoft-azure-kubernetes-service": "CD-V2-AZURE-KUBERNETES-SERVICE-AKS",
    "rds": "CD-V2-AWS-RDS",
    "rest-full-web-service": "CD-V2-RESTFUL-WEB-SERVICE",
    "s3": "CD-V2-AWS-S3",
    "sns": "CD-V2-AWS-SNS-SIMPLE-NOTIFICATION-SERVICE",
    "sqs-simple-queue-service": "CD-V2-AWS-SQS",
    # Approximations — closest semantic match, no exact equivalent in library.
    "host_container": "CD-V2-DOCKER-CONTAINER",
    "kubernetes-node": "CD-V2-KUBERNETES-POD",
    "oidc-provider": "CD-V2-OAUTH2-AUTHORIZATION-SERVER",
    "oidc-relying-party": "CD-V2-OAUTH2-CLIENT-APPLICATION",
}


def fetch_components(base_url: str, token: str) -> list[dict]:
    items: list[dict] = []
    page = 0
    size = 20
    while True:
        url = f"{base_url.rstrip('/')}/api/v2/components?page={page}&size={size}"
        for attempt in range(8):
            try:
                req = urllib.request.Request(
                    url,
                    headers={
                        "api-token": token,
                        "Accept": "application/hal+json",
                        "User-Agent": "archithreat-regen/1.0",
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
        if (page % 10) == 0:
            print(
                f"  page {page}/{meta['totalPages'] - 1} ({len(items)}/{meta['totalElements']})",
                file=sys.stderr,
            )
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
    items = fetch_components(base, token)
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps(items))
    print(f"cached {len(items)} components → {cache}", file=sys.stderr)
    return items


def remap_ref(old: str, present: set[str]) -> str | None:
    """Return the new CD-V2 ref for ``old``, or None if no candidate.

    Lookup order: manual override → already CD-V2-* and present → mechanical
    transform (CD-V2- + uppercase, with optional CD- strip) → None.
    """
    if old in MANUAL_OVERRIDES:
        new = MANUAL_OVERRIDES[old]
        return new if new in present else None
    if old.startswith("CD-V2-") and old in present:
        return old
    if old.startswith("CD-"):
        candidate = "CD-V2-" + old[3:]
    else:
        candidate = "CD-V2-" + old.upper().replace("_", "-")
    return candidate if candidate in present else None


def rewrite_yaml(yaml_text: str, present: set[str]) -> tuple[str, dict[str, str], list[str]]:
    remap: dict[str, str] = {}
    unmapped: set[str] = set()

    def remember(ref: str) -> str:
        if ref in remap:
            return remap[ref]
        new = remap_ref(ref, present)
        if new is None:
            unmapped.add(ref)
            return ref  # keep as-is so manual fixup is possible
        remap[ref] = new
        return new

    out_lines: list[str] = []
    for line in yaml_text.splitlines(keepends=True):
        # Substitute every ir.componentDefinition.ref=<x> in the line. A line
        # may contain only one, but the regex makes that explicit.
        def _sub_style(m: re.Match[str]) -> str:
            return f"ir.componentDefinition.ref={remember(m.group(1))}"

        new_line = REF_PATTERN.sub(_sub_style, line)
        type_match = TYPE_PATTERN.match(new_line)
        if type_match:
            new_line = f"{type_match.group(1)}{remember(type_match.group(2))}\n"
        out_lines.append(new_line)
    return "".join(out_lines), remap, sorted(unmapped)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--cache",
        type=Path,
        default=DEFAULT_CACHE,
        help=(
            "JSON file to read/write the components dump. Defaults to "
            "scripts/.iriusrisk-components.json (gitignored)."
        ),
    )
    ap.add_argument(
        "--refresh",
        action="store_true",
        help="Refetch from API even if the cache exists.",
    )
    ap.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the diff but don't write iriusrisk.yaml.",
    )
    args = ap.parse_args()

    items = load_or_fetch(args.cache, args.refresh)
    active = [i for i in items if "eprecated" not in i["category"]["name"]]
    present = {i["referenceId"] for i in active}
    print(f"library: {len(active)} active components", file=sys.stderr)

    yaml_text = YAML_PATH.read_text()
    new_text, remap, unmapped = rewrite_yaml(yaml_text, present)

    print(f"\n{len(remap)} ref(s) remapped:", file=sys.stderr)
    for old, new in sorted(remap.items()):
        if old != new:
            print(f"  {old:45} -> {new}", file=sys.stderr)

    if unmapped:
        print(f"\n{len(unmapped)} ref(s) UNMAPPED (kept as-is):", file=sys.stderr)
        for u in unmapped:
            print(f"  {u}", file=sys.stderr)

    if args.dry_run:
        print("\n--dry-run: not writing", file=sys.stderr)
        return

    YAML_PATH.write_text(new_text)
    print(f"\nwrote {YAML_PATH}", file=sys.stderr)


if __name__ == "__main__":
    main()
