"""Inventory mode: parser + resolver report, no emission. Target-independent."""

from __future__ import annotations

import json
import os
import statistics
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
from typing import Any, Literal

from .mappings import load_default_mapping
from .mappings.base import BaseMapping
from .model import OpenExchangeModel, ResolvedModel
from .parser import parse_bytes, parse_path
from .resolver import EXTERNAL_ID, UNZONED_ID, resolve_with_synthetic

ReportFormat = Literal["text", "json", "markdown"]


@dataclass
class Distribution:
    median: float = 0.0
    p95: float = 0.0
    max: int = 0


@dataclass
class WarningSummary:
    code: str
    count: int
    sample_ids: list[str] = field(default_factory=list)


@dataclass
class InventoryReport:
    model_name: str
    counts_by_type: dict[str, int]
    counts_by_layer: dict[str, int]
    realization_coverage: dict[str, int]
    zone_coverage: dict[str, int]
    cohosting_distribution: Distribution
    external_actor_count: int
    external_actor_touches: int
    warnings: list[WarningSummary]
    skipped: list[WarningSummary]

    def to_text(self) -> str:
        lines: list[str] = []
        lines.append(f"archithreat inventory: {self.model_name}")
        lines.append("=" * 60)
        lines.append("\nCounts by ArchiMate type:")
        for t, c in sorted(self.counts_by_type.items()):
            lines.append(f"  {t:32s} {c:5d}")
        lines.append("\nCounts by layer:")
        for layer, c in sorted(self.counts_by_layer.items()):
            lines.append(f"  {layer:32s} {c:5d}")
        lines.append("\nRealization coverage:")
        for k, v in self.realization_coverage.items():
            lines.append(f"  {k:32s} {v:5d}")
        lines.append("\nZone coverage:")
        for k, v in self.zone_coverage.items():
            lines.append(f"  {k:32s} {v:5d}")
        lines.append("\nCo-hosting (components per host):")
        d = self.cohosting_distribution
        lines.append(f"  median {d.median:.1f}  p95 {d.p95:.1f}  max {d.max}")
        lines.append(
            f"\nExternal actors: {self.external_actor_count} "
            f"(touch {self.external_actor_touches} App/Tech elements)"
        )
        if self.warnings:
            lines.append("\nWarnings:")
            for w in self.warnings:
                ids = ", ".join(w.sample_ids)
                lines.append(f"  [{w.code}] x{w.count}  e.g. {ids}")
        if self.skipped:
            lines.append("\nSkipped:")
            for s in self.skipped:
                ids = ", ".join(s.sample_ids)
                lines.append(f"  [{s.code}] x{s.count}  e.g. {ids}")
        return "\n".join(lines) + "\n"

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2, sort_keys=True)

    def to_markdown(self) -> str:
        # simple, readable report; not the place for fancy tables.
        out: list[str] = []
        out.append(f"# Inventory: {self.model_name}\n")
        out.append("## Counts by type\n")
        for t, c in sorted(self.counts_by_type.items()):
            out.append(f"- `{t}`: {c}")
        out.append("\n## Counts by layer\n")
        for layer, c in sorted(self.counts_by_layer.items()):
            out.append(f"- `{layer}`: {c}")
        out.append("\n## Realization coverage\n")
        for k, v in self.realization_coverage.items():
            out.append(f"- {k}: {v}")
        out.append("\n## Zone coverage\n")
        for k, v in self.zone_coverage.items():
            out.append(f"- {k}: {v}")
        d = self.cohosting_distribution
        out.append(f"\n## Co-hosting\n\nmedian {d.median:.1f} / p95 {d.p95:.1f} / max {d.max}\n")
        out.append(
            f"\n## External actors\n\n{self.external_actor_count} actors touching "
            f"{self.external_actor_touches} App/Tech elements\n"
        )
        if self.warnings:
            out.append("\n## Warnings\n")
            for w in self.warnings:
                out.append(f"- `{w.code}` ×{w.count} — e.g. {', '.join(w.sample_ids)}")
        if self.skipped:
            out.append("\n## Skipped\n")
            for s in self.skipped:
                out.append(f"- `{s.code}` ×{s.count} — e.g. {', '.join(s.sample_ids)}")
        return "\n".join(out) + "\n"


def inventory_bytes(data: bytes, mapping: BaseMapping | None = None) -> InventoryReport:
    model = parse_bytes(data)
    return _build_report(model, mapping or load_default_mapping())


def inventory_path(
    path: str | os.PathLike[str], mapping: BaseMapping | None = None
) -> InventoryReport:
    model = parse_path(path)
    return _build_report(model, mapping or load_default_mapping())


def _build_report(model: OpenExchangeModel, mapping: BaseMapping) -> InventoryReport:
    counts_by_type: Counter[str] = Counter()
    counts_by_layer: Counter[str] = Counter()
    for el in model.elements.values():
        counts_by_type[el.archimate_type] += 1
        counts_by_layer[el.layer] += 1

    resolved = resolve_with_synthetic(model, mapping)
    realization_coverage = _realization_stats(model, resolved)
    zone_coverage = _zone_stats(model, resolved)
    cohosting = _cohosting_distribution(resolved)
    ext_count, ext_touches = _external_actor_stats(resolved)

    warnings = _summarize(resolved.warnings)
    skipped = _summarize(resolved.skipped)

    return InventoryReport(
        model_name=model.name,
        counts_by_type=dict(counts_by_type),
        counts_by_layer=dict(counts_by_layer),
        realization_coverage=realization_coverage,
        zone_coverage=zone_coverage,
        cohosting_distribution=cohosting,
        external_actor_count=ext_count,
        external_actor_touches=ext_touches,
        warnings=warnings,
        skipped=skipped,
    )


def _realization_stats(model: OpenExchangeModel, resolved: ResolvedModel) -> dict[str, int]:
    app_total = sum(
        1 for e in model.elements.values() if e.archimate_type == "ApplicationComponent"
    )
    realized = {
        link.application_component_id
        for link in resolved.realization_links
        if link.node_id is not None
    }
    orphans = app_total - len(realized)
    return {
        "application_components_total": app_total,
        "with_node_realization": len(realized),
        "orphans": orphans,
    }


def _zone_stats(model: OpenExchangeModel, resolved: ResolvedModel) -> dict[str, int]:
    inside = sum(
        1 for c in resolved.components.values() if c.zone_id not in (UNZONED_ID, EXTERNAL_ID)
    )
    unzoned = sum(1 for c in resolved.components.values() if c.zone_id == UNZONED_ID)
    external = sum(1 for c in resolved.components.values() if c.zone_id == EXTERNAL_ID)
    real_zones = sum(1 for z in resolved.zones.values() if not z.is_synthetic)
    return {
        "real_zones": real_zones,
        "components_inside_real_zones": inside,
        "components_unzoned": unzoned,
        "components_external": external,
    }


def _cohosting_distribution(resolved: ResolvedModel) -> Distribution:
    per_host: defaultdict[str, int] = defaultdict(int)
    for c in resolved.components.values():
        if c.host_node_id is not None:
            per_host[c.host_node_id] += 1
    counts = sorted(per_host.values())
    if not counts:
        return Distribution()
    median = statistics.median(counts)
    if len(counts) == 1:
        p95: float = float(counts[0])
    else:
        # nearest-rank p95
        idx = max(0, int(round(0.95 * (len(counts) - 1))))
        p95 = float(counts[idx])
    return Distribution(median=float(median), p95=p95, max=max(counts))


def _external_actor_stats(resolved: ResolvedModel) -> tuple[int, int]:
    actor_ids = {c.id for c in resolved.components.values() if c.is_external_actor}
    touches = 0
    for conn in resolved.connections:
        if conn.source_component_id in actor_ids or conn.target_component_id in actor_ids:
            touches += 1
    return len(actor_ids), touches


def _summarize(warnings: list[Any]) -> list[WarningSummary]:
    bucket: defaultdict[str, list[str]] = defaultdict(list)
    counts: Counter[str] = Counter()
    for w in warnings:
        counts[w.code] += 1
        if len(bucket[w.code]) < 5 and w.element_id:
            bucket[w.code].append(w.element_id)
    return [
        WarningSummary(code=code, count=counts[code], sample_ids=bucket[code])
        for code in sorted(counts)
    ]


__all__ = [
    "InventoryReport",
    "ReportFormat",
    "inventory_bytes",
    "inventory_path",
]
