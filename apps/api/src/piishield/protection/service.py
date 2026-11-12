"""The protect pipeline: scan, decide review vs. protect, apply the masking method,
record the scan event and audit entry. This is the one place ``Finding.matched_text`` is
read outside the detectors module itself, and it never writes that text anywhere except
as the input to a masking function or ``vault.tokenize`` (which immediately encrypts it).

Request lifecycle (mirrors PLAN.md's "Request lifecycle" section exactly):
1. Load the project's policy (cached snapshot).
2. Run detectors; checksum-invalid matches are already excluded by the detectors module.
3. Findings below the policy's confidence threshold go to the review queue instead of
   being auto-protected, UNLESS the category is required (then AC10 forces protection
   regardless, and it is still flagged for review per PLAN.md's step 3).
4. Apply the method: policy default, per-call override, or refuse (AC10) if a required
   category was asked to be skipped.
5. Return protected content plus the finding list; the vault mapping and any original
   value never appear in this response (AC6).
6. Record the scan (counts/categories only) and commit.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from piishield.audit.service import Actor
from piishield.audit.service import record as audit_record
from piishield.core.kv import KV
from piishield.core.metrics import FINDINGS, PROTECTED, SCANS
from piishield.core.sealing import Sealer
from piishield.detectors.recognizers import Finding
from piishield.detectors.service import scan as run_scan
from piishield.policies.service import PolicySnapshot
from piishield.policies.service import load as load_policy
from piishield.projects.service import ensure_project
from piishield.protection import json_walk
from piishield.protection import repository as scan_repo
from piishield.protection.exceptions import RequiredCategoryUnmaskedError
from piishield.protection.masking import apply_many, full_mask, partial_mask, redact
from piishield.review.service import queue_finding
from piishield.vault.service import tokenize as vault_tokenize


@dataclass(frozen=True, slots=True)
class ProtectedFinding:
    category: str
    start: int
    end: int
    confidence: float
    checksum_valid: bool | None
    recognizer: str
    method: str
    placeholder: str | None
    in_review: bool


def _effective_method(
    policy: PolicySnapshot, category: str, overrides: dict[str, str], skip: set[str]
) -> str:
    if category in skip:
        if policy.is_required(category):
            raise RequiredCategoryUnmaskedError(category)
        return "skip"
    return overrides.get(category, policy.method_for(category))


async def _apply_method(
    session: AsyncSession,
    kv: KV,
    sealer: Sealer,
    actor: Actor,
    project_id: uuid.UUID,
    scope_id: str,
    policy: PolicySnapshot,
    finding: Finding,
    method: str,
) -> tuple[str, str | None]:
    """Returns (replacement_text, placeholder_or_none)."""
    if method == "skip":
        return finding.matched_text, None
    if method == "full_mask":
        return full_mask(finding.matched_text), None
    if method == "partial_mask":
        return partial_mask(finding.matched_text, policy.partial_mask_reveal), None
    if method == "redact":
        return redact(finding.category), None
    placeholder = await vault_tokenize(
        session, kv, sealer, actor, project_id, scope_id, finding.category, finding.matched_text
    )
    return placeholder, placeholder


async def _protect_one_text(
    session: AsyncSession,
    kv: KV,
    sealer: Sealer,
    actor: Actor,
    project_id: uuid.UUID,
    text: str,
    policy: PolicySnapshot,
    overrides: dict[str, str],
    skip: set[str],
    scope_id: str,
) -> tuple[str, list[ProtectedFinding]]:
    """The scan-and-mask core for one string, with no commit and no audit/scan-event
    write: callers (``protect_text``, ``protect_json``) batch those once per request so a
    JSON payload with many leaves produces exactly one scan event and one audit row, not
    one per leaf."""
    findings = await run_scan(session, actor.scope, project_id, text)
    replacements: list[tuple[int, int, str]] = []
    out: list[ProtectedFinding] = []
    for finding in findings:
        required = policy.is_required(finding.category)
        below_threshold = finding.confidence < policy.confidence_threshold
        if below_threshold and not required:
            queue_finding(session, actor.org_id, project_id, finding, already_protected=False)
            out.append(
                ProtectedFinding(
                    finding.category,
                    finding.start,
                    finding.end,
                    finding.confidence,
                    finding.checksum_valid,
                    finding.recognizer,
                    "review",
                    None,
                    True,
                )
            )
            continue  # not auto-protected; left as-is in the output, flagged for review

        method = _effective_method(policy, finding.category, overrides, skip)
        replacement, placeholder = await _apply_method(
            session, kv, sealer, actor, project_id, scope_id, policy, finding, method
        )
        replacements.append((finding.start, finding.end, replacement))
        if below_threshold and required:
            queue_finding(session, actor.org_id, project_id, finding, already_protected=True)
        out.append(
            ProtectedFinding(
                finding.category,
                finding.start,
                finding.end,
                finding.confidence,
                finding.checksum_valid,
                finding.recognizer,
                method,
                placeholder,
                below_threshold,
            )
        )
    return apply_many(text, replacements), out


async def protect_text(
    session: AsyncSession,
    kv: KV,
    sealer: Sealer,
    actor: Actor,
    project_id: uuid.UUID,
    text: str,
    *,
    method_overrides: dict[str, str] | None = None,
    skip_categories: list[str] | None = None,
    scope_id: str | None = None,
    source: str = "text",
) -> tuple[str, list[ProtectedFinding], str]:
    await ensure_project(session, actor.scope, project_id)
    scope_id = scope_id or uuid.uuid4().hex
    policy = await load_policy(session, kv, actor.scope, project_id)
    protected, out = await _protect_one_text(
        session,
        kv,
        sealer,
        actor,
        project_id,
        text,
        policy,
        method_overrides or {},
        set(skip_categories or []),
        scope_id,
    )
    review_count = sum(1 for f in out if f.in_review)
    categories = [f.category for f in out]
    scan_repo.record_scan(
        session, actor.org_id, project_id, source, len(out), review_count, categories
    )
    audit_record(
        session,
        actor,
        "scan",
        project_id=project_id,
        finding_count=len(out),
        categories=categories,
        source=source,
    )
    await session.commit()
    SCANS.labels(source=source).inc()
    for f in out:
        FINDINGS.labels(category=f.category).inc()
        if f.method and f.method != "skip":
            PROTECTED.labels(method=f.method).inc()
    return protected, out, scope_id


async def protect_json(
    session: AsyncSession,
    kv: KV,
    sealer: Sealer,
    actor: Actor,
    project_id: uuid.UUID,
    payload: object,
    *,
    method_overrides: dict[str, str] | None = None,
    skip_categories: list[str] | None = None,
    scope_id: str | None = None,
) -> tuple[object, list[ProtectedFinding], str]:
    """AC7: every string leaf is scanned and protected independently; the returned
    structure has identical keys, nesting and array order/length to the input."""
    await ensure_project(session, actor.scope, project_id)
    scope_id = scope_id or uuid.uuid4().hex
    overrides = method_overrides or {}
    skip = set(skip_categories or [])
    policy = await load_policy(session, kv, actor.scope, project_id)
    leaf_replacements: dict[str, str] = {}
    all_findings: list[ProtectedFinding] = []

    for path, leaf in json_walk.walk_strings(payload):
        if not leaf:
            continue
        protected_leaf, findings = await _protect_one_text(
            session, kv, sealer, actor, project_id, leaf, policy, overrides, skip, scope_id
        )
        if protected_leaf != leaf:
            leaf_replacements[path] = protected_leaf
        all_findings.extend(findings)

    rebuilt = json_walk.rebuild(payload, leaf_replacements)
    review_count = sum(1 for f in all_findings if f.in_review)
    categories = [f.category for f in all_findings]
    scan_repo.record_scan(
        session, actor.org_id, project_id, "json", len(all_findings), review_count, categories
    )
    audit_record(
        session,
        actor,
        "scan",
        project_id=project_id,
        finding_count=len(all_findings),
        categories=categories,
        source="json",
    )
    await session.commit()
    SCANS.labels(source="json").inc()
    for f in all_findings:
        FINDINGS.labels(category=f.category).inc()
        if f.method and f.method != "skip":
            PROTECTED.labels(method=f.method).inc()
    return rebuilt, all_findings, scope_id
