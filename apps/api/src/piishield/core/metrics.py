"""Prometheus counters for the domain events an operator actually wants to graph.
Labels are bounded (category, method): never a request-specific value like a project id
or a finding's matched text."""

from __future__ import annotations

from prometheus_client import Counter

SCANS = Counter(
    "piishield_scans_total",
    "Detection calls (scan, protect, document, database-scan, AI gateway protect)",
    ["source"],
)
FINDINGS = Counter(
    "piishield_findings_total",
    "Findings detected, by category",
    ["category"],
)
PROTECTED = Counter(
    "piishield_protected_total",
    "Findings actually protected, by method",
    ["method"],
)
DETOKENIZE = Counter(
    "piishield_detokenize_total",
    "Vault detokenize calls, by outcome",
    ["outcome"],
)
