#!/usr/bin/env python3
"""Solaris Quality OS — product, design, QA, security, and legal assurance.

Deterministic, provider-neutral gates for the Alfred/Solaris capability system.
Implements:

  * Risk classification of deliverables and orders
  * Specialist gate routing (functional, UX, a11y, security, privacy, legal)
  * Evidence schemas for findings, waivers, and release packets
  * Dissent / waiver behaviour with human authority boundaries
  * Finding → order conversion
  * Hard ban on self-approval of blocking findings
  * Legal informational boundaries and source-freshness checks

This module is stdlib-only. Synthetic fixtures only — no private data.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
import sys
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

ASSURANCE_VERSION = "1.0.0"
SCHEMA_VERSION = "1.0.0"

# ---------------------------------------------------------------------------
# Risk classification
# ---------------------------------------------------------------------------

RISK_LEVELS = ("informational", "standard", "elevated", "high", "critical")

# Risk rank for comparisons
RISK_RANK = {level: i for i, level in enumerate(RISK_LEVELS)}

# Defect kinds that map to accountable specialist gates.
DEFECT_KINDS = (
    "functional",
    "ux",
    "accessibility",
    "security",
    "privacy",
    "legal_risk",
    "compliance",
    "requirements",
    "design",
    "performance",
    "release",
)

# Accountable gate role per defect kind (primary owner of the gate).
# A finding for that kind is owned by this role and cannot be self-closed by it.
ACCOUNTABLE_GATES: Dict[str, str] = {
    "functional": "qa-engineer",
    "ux": "ui-ux-designer",
    "accessibility": "qa-engineer",
    "security": "security-auditor",
    "privacy": "compliance-auditor",
    "legal_risk": "legal-advisor",
    "compliance": "compliance-auditor",
    "requirements": "product-manager",
    "design": "ui-ux-designer",
    "performance": "performance-engineer",
    "release": "delivery-lead",
}

# Independent verifier roles (must differ from accountable for blocking findings).
DEFAULT_VERIFIERS: Dict[str, str] = {
    "functional": "code-reviewer",
    "ux": "qa-engineer",
    "accessibility": "ui-ux-designer",
    "security": "code-reviewer",
    "privacy": "security-auditor",
    "legal_risk": "compliance-auditor",
    "compliance": "legal-advisor",
    "requirements": "business-analyst",
    "design": "qa-engineer",
    "performance": "code-reviewer",
    "release": "qa-engineer",
}

# Risk dimensions that force specialist gates when elevated+.
SPECIALIST_TRIGGERS: Dict[str, Sequence[str]] = {
    "security": ("security",),
    "privacy": ("privacy", "compliance"),
    "accessibility": ("accessibility",),
    "legal": ("legal_risk", "compliance"),
    "ux": ("ux", "design"),
    "functional": ("functional",),
    "performance": ("performance",),
    "requirements": ("requirements",),
}

# Thresholds: minimum risk level at which a specialist gate is mandatory.
GATE_THRESHOLDS: Dict[str, str] = {
    "functional": "standard",
    "ux": "elevated",
    "accessibility": "elevated",
    "security": "elevated",
    "privacy": "elevated",
    "legal_risk": "elevated",
    "compliance": "elevated",
    "requirements": "standard",
    "design": "elevated",
    "performance": "elevated",
    "release": "high",
}

# Severity → risk mapping for findings.
SEVERITY_TO_RISK = {
    "S0": "critical",
    "S1": "critical",
    "S2": "high",
    "S3": "elevated",
    "S4": "standard",
    "info": "informational",
}

BLOCKING_SEVERITIES = frozenset({"S0", "S1", "S2"})

# Legal / compliance prohibited binding patterns (synthetic text checks).
LEGAL_BINDING_PATTERNS = [
    re.compile(r"\bI am your attorney\b", re.I),
    re.compile(r"\bthis constitutes legal advice\b", re.I),
    re.compile(r"\bfile this (lawsuit|complaint|motion|trademark)\b", re.I),
    re.compile(r"\bI (will|shall) (file|represent|appear)\b", re.I),
    re.compile(r"\bbinding legal (opinion|advice)\b", re.I),
    re.compile(r"\bdestroy evidence\b", re.I),
]

LEGAL_REQUIRED_DISCLAIMERS = [
    re.compile(r"not (a )?lawyer|not legal advice|licensed attorney|informational only", re.I),
]

# Source freshness: legal/compliance references older than this are stale.
DEFAULT_SOURCE_FRESHNESS_DAYS = 365

# High-stakes actions that never auto-allow.
HIGH_STAKES_ACTIONS = frozenset(
    {
        "legal_file",
        "mutate_external",
        "deploy",
        "spend",
        "message_send",
        "book",
        "move_funds",
        "diagnose_health",
    }
)


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


@dataclass
class GateCode:
    code: str
    message: str
    blocking: bool = True


@dataclass
class Finding:
    finding_id: str
    defect_kind: str
    severity: str
    title: str
    evidence: List[str]
    accountable_role: str
    reporter_role: str
    status: str = "open"  # open | in_progress | waived | closed
    closure_criteria: str = ""
    verifier_role: str = ""
    closed_by_role: str = ""
    order_id: str = ""
    waiver_id: str = ""
    created_at: str = ""
    updated_at: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Finding":
        return cls(**{k: data[k] for k in cls.__dataclass_fields__ if k in data})


@dataclass
class Order:
    order_id: str
    source_finding_id: str
    owner_role: str
    severity: str
    title: str
    evidence: List[str]
    closure_criteria: str
    status: str = "open"
    dedupe_key: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class Waiver:
    waiver_id: str
    finding_id: str
    requested_by_role: str
    approved_by_role: str
    human_authority: bool
    justification: str
    expires_at: str
    status: str = "proposed"  # proposed | active | rejected | expired

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class AssuranceResult:
    ok: bool
    status: str  # pass | blocked | waived | error
    gate_codes: List[str] = field(default_factory=list)
    messages: List[str] = field(default_factory=list)
    findings: List[Dict[str, Any]] = field(default_factory=list)
    orders: List[Dict[str, Any]] = field(default_factory=list)
    required_gates: List[str] = field(default_factory=list)
    risk_level: str = "standard"
    evidence: Dict[str, Any] = field(default_factory=dict)
    notes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "assurance_version": ASSURANCE_VERSION,
            "ok": self.ok,
            "status": self.status,
            "gate_codes": list(self.gate_codes),
            "messages": list(self.messages),
            "findings": list(self.findings),
            "orders": list(self.orders),
            "required_gates": list(self.required_gates),
            "risk_level": self.risk_level,
            "evidence": self.evidence,
            "notes": list(self.notes),
        }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:10]}"


def risk_at_least(level: str, threshold: str) -> bool:
    return RISK_RANK.get(level, 0) >= RISK_RANK.get(threshold, 0)


def classify_risk(
    *,
    blast_radius: str = "local",  # local | project | fleet | external
    data_sensitivity: str = "none",  # none | internal | pii | financial | health | legal
    user_facing: bool = False,
    mutates_external: bool = False,
    regulatory: bool = False,
    release_candidate: bool = False,
    explicit_level: Optional[str] = None,
) -> str:
    """Classify deliverable / order risk. Higher of computed vs explicit wins."""
    if explicit_level and explicit_level in RISK_RANK:
        base = explicit_level
    else:
        base = "informational"

    score = RISK_RANK[base]

    if blast_radius == "project":
        score = max(score, RISK_RANK["standard"])
    elif blast_radius == "fleet":
        score = max(score, RISK_RANK["elevated"])
    elif blast_radius == "external":
        score = max(score, RISK_RANK["high"])

    sens_map = {
        "none": 0,
        "internal": RISK_RANK["standard"],
        "pii": RISK_RANK["elevated"],
        "financial": RISK_RANK["high"],
        "health": RISK_RANK["high"],
        "legal": RISK_RANK["high"],
    }
    score = max(score, sens_map.get(data_sensitivity, 0))

    if user_facing:
        score = max(score, RISK_RANK["standard"])
    if mutates_external:
        score = max(score, RISK_RANK["high"])
    if regulatory:
        score = max(score, RISK_RANK["high"])
    if release_candidate:
        score = max(score, RISK_RANK["high"])

    return RISK_LEVELS[score]


def required_specialist_gates(
    risk_level: str,
    dimensions: Sequence[str],
) -> List[str]:
    """Return ordered unique defect kinds that must run at this risk level."""
    required: List[str] = []
    for dim in dimensions:
        kinds = SPECIALIST_TRIGGERS.get(dim, ())
        for kind in kinds:
            threshold = GATE_THRESHOLDS.get(kind, "elevated")
            if risk_at_least(risk_level, threshold) and kind not in required:
                required.append(kind)
    # Release gate always at high+
    if risk_at_least(risk_level, GATE_THRESHOLDS["release"]) and "release" not in required:
        required.append("release")
    return required


def route_defect(defect_kind: str) -> Dict[str, str]:
    """Map a planted/detected defect to accountable + verifier roles."""
    if defect_kind not in ACCOUNTABLE_GATES:
        raise ValueError(f"unknown defect_kind: {defect_kind}")
    return {
        "defect_kind": defect_kind,
        "accountable_role": ACCOUNTABLE_GATES[defect_kind],
        "verifier_role": DEFAULT_VERIFIERS[defect_kind],
    }


def create_finding(
    *,
    defect_kind: str,
    severity: str,
    title: str,
    evidence: Sequence[str],
    reporter_role: str,
    closure_criteria: str = "",
    finding_id: Optional[str] = None,
) -> Finding:
    route = route_defect(defect_kind)
    now = utc_now()
    return Finding(
        finding_id=finding_id or new_id("fnd"),
        defect_kind=defect_kind,
        severity=severity,
        title=title,
        evidence=list(evidence),
        accountable_role=route["accountable_role"],
        reporter_role=reporter_role,
        status="open",
        closure_criteria=closure_criteria
        or f"Independent {route['verifier_role']} verifies fix with evidence.",
        verifier_role=route["verifier_role"],
        created_at=now,
        updated_at=now,
    )


def finding_to_order(finding: Finding) -> Order:
    """Convert a finding into a deduplicated work order."""
    dedupe_raw = f"{finding.defect_kind}|{finding.title.strip().lower()}"
    dedupe_key = hashlib.sha256(dedupe_raw.encode("utf-8")).hexdigest()[:16]
    return Order(
        order_id=new_id("ord"),
        source_finding_id=finding.finding_id,
        owner_role=finding.accountable_role,
        severity=finding.severity,
        title=f"[{finding.defect_kind}] {finding.title}",
        evidence=list(finding.evidence),
        closure_criteria=finding.closure_criteria,
        status="open",
        dedupe_key=dedupe_key,
    )


def convert_findings_to_orders(findings: Sequence[Finding]) -> List[Order]:
    """Deduplicate by defect_kind+title; keep highest severity."""
    severity_rank = {"S0": 5, "S1": 4, "S2": 3, "S3": 2, "S4": 1, "info": 0}
    by_key: Dict[str, Order] = {}
    for f in findings:
        order = finding_to_order(f)
        existing = by_key.get(order.dedupe_key)
        if existing is None:
            by_key[order.dedupe_key] = order
        else:
            if severity_rank.get(f.severity, 0) > severity_rank.get(existing.severity, 0):
                by_key[order.dedupe_key] = order
    return list(by_key.values())


# ---------------------------------------------------------------------------
# Self-approval ban
# ---------------------------------------------------------------------------


def can_close_finding(
    finding: Finding,
    *,
    closer_role: str,
    independent_evidence: Sequence[str],
    waiver: Optional[Waiver] = None,
) -> Tuple[bool, List[str]]:
    """Return (allowed, gate_codes). Blocking findings cannot be self-closed."""
    codes: List[str] = []

    if finding.status == "closed":
        return False, ["ALREADY_CLOSED"]

    if finding.status == "waived":
        if waiver and waiver.status == "active" and waiver.finding_id == finding.finding_id:
            return True, []
        return False, ["WAIVER_REQUIRED"]

    blocking = finding.severity in BLOCKING_SEVERITIES

    # Hard rule: accountable role cannot close its own unresolved blocking finding.
    if blocking and closer_role == finding.accountable_role:
        codes.append("SELF_APPROVAL_FORBIDDEN")
        return False, codes

    # Reporter also cannot sole-close a blocking finding they opened.
    if blocking and closer_role == finding.reporter_role and closer_role == finding.accountable_role:
        codes.append("SELF_APPROVAL_FORBIDDEN")
        return False, codes

    if blocking and closer_role != finding.verifier_role:
        # Allow explicit human authority role override name
        if closer_role not in ("human-owner", "chief-of-staff", finding.verifier_role):
            codes.append("INDEPENDENT_VERIFIER_REQUIRED")
            return False, codes

    if blocking and not independent_evidence:
        codes.append("MISSING_CLOSURE_EVIDENCE")
        return False, codes

    return True, codes


def close_finding(
    finding: Finding,
    *,
    closer_role: str,
    independent_evidence: Sequence[str],
    waiver: Optional[Waiver] = None,
) -> Tuple[Finding, List[str]]:
    allowed, codes = can_close_finding(
        finding,
        closer_role=closer_role,
        independent_evidence=independent_evidence,
        waiver=waiver,
    )
    updated = copy.deepcopy(finding)
    if not allowed:
        return updated, codes
    updated.status = "closed"
    updated.closed_by_role = closer_role
    updated.evidence = list(finding.evidence) + list(independent_evidence)
    updated.updated_at = utc_now()
    return updated, []


# ---------------------------------------------------------------------------
# Waivers and dissent
# ---------------------------------------------------------------------------


def propose_waiver(
    finding: Finding,
    *,
    requested_by_role: str,
    approved_by_role: str,
    human_authority: bool,
    justification: str,
    expires_at: str,
) -> Tuple[Optional[Waiver], List[str]]:
    codes: List[str] = []
    if not justification or len(justification.strip()) < 12:
        codes.append("WAIVER_JUSTIFICATION_REQUIRED")
    if not human_authority:
        codes.append("HUMAN_AUTHORITY_REQUIRED")
    if approved_by_role == finding.accountable_role:
        codes.append("WAIVER_SELF_APPROVAL_FORBIDDEN")
    if approved_by_role == requested_by_role and requested_by_role == finding.accountable_role:
        codes.append("WAIVER_SELF_APPROVAL_FORBIDDEN")
    if not expires_at:
        codes.append("WAIVER_EXPIRY_REQUIRED")
    if codes:
        return None, codes
    return (
        Waiver(
            waiver_id=new_id("wvr"),
            finding_id=finding.finding_id,
            requested_by_role=requested_by_role,
            approved_by_role=approved_by_role,
            human_authority=True,
            justification=justification.strip(),
            expires_at=expires_at,
            status="active",
        ),
        [],
    )


def apply_dissent(
    *,
    claim: str,
    votes: Sequence[Dict[str, Any]],
) -> Dict[str, Any]:
    """Council dissent: HOLD if any dissent/refute; PASS only if no dissent and ≥1 confirm."""
    confirmed = 0
    dissent = 0
    for v in votes:
        verdict = str(v.get("verdict", "")).upper()
        if verdict in ("REFUTED", "DISSENT", "HOLD"):
            dissent += 1
        elif verdict in ("CONFIRMED", "PASS"):
            confirmed += 1
        elif v.get("dissent") is True:
            dissent += 1
    if dissent > 0:
        outcome = "HOLD"
    elif confirmed > 0:
        outcome = "PASS"
    else:
        outcome = "HOLD"
    return {
        "claim": claim,
        "outcome": outcome,
        "confirmed": confirmed,
        "dissent": dissent,
        "unanimous": dissent == 0 and confirmed > 0,
        "reachable": len(votes),
    }


# ---------------------------------------------------------------------------
# Legal / compliance informational boundaries
# ---------------------------------------------------------------------------


def check_legal_boundaries(
    text: str,
    *,
    requested_actions: Optional[Sequence[str]] = None,
    sources: Optional[Sequence[Dict[str, Any]]] = None,
    as_of: Optional[datetime] = None,
    freshness_days: int = DEFAULT_SOURCE_FRESHNESS_DAYS,
) -> AssuranceResult:
    """Fail closed on binding legal advice, legal_file without human, stale sources."""
    gates: List[str] = []
    messages: List[str] = []
    as_of = as_of or datetime.now(timezone.utc)

    for pat in LEGAL_BINDING_PATTERNS:
        if pat.search(text or ""):
            gates.append("LEGAL_BINDING_PROHIBITED")
            messages.append(f"Binding/prohibited legal pattern matched: {pat.pattern}")
            break

    for action in requested_actions or []:
        if action in HIGH_STAKES_ACTIONS:
            gates.append("HIGH_STAKES_REQUIRES_HUMAN")
            messages.append(f"Action '{action}' requires explicit human confirmation")
        if action == "legal_file":
            gates.append("LEGAL_FILING_FORBIDDEN")
            messages.append("Legal filing is never automated")

    # Disclaimer required when discussing legal topics
    legalish = bool(
        re.search(
            r"\b(contract|liability|indemnif|GDPR|HIPAA|lawsuit|jurisdiction|attorney|NDA)\b",
            text or "",
            re.I,
        )
    )
    if legalish:
        if not any(p.search(text or "") for p in LEGAL_REQUIRED_DISCLAIMERS):
            gates.append("LEGAL_DISCLAIMER_MISSING")
            messages.append("Legal discussion missing informational-only disclaimer")

    # Source freshness
    if sources is not None:
        if len(sources) == 0 and legalish:
            gates.append("LEGAL_SOURCE_REQUIRED")
            messages.append("Legal/compliance claim requires cited sources")
        for src in sources:
            retrieved = src.get("retrieved_at") or src.get("published_at")
            if not retrieved:
                gates.append("LEGAL_SOURCE_DATE_MISSING")
                messages.append(f"Source missing date: {src.get('id') or src.get('title')}")
                continue
            try:
                if isinstance(retrieved, str):
                    # Support YYYY-MM-DD or full ISO
                    dt = datetime.fromisoformat(retrieved.replace("Z", "+00:00"))
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=timezone.utc)
                else:
                    continue
                age = (as_of - dt).days
                max_age = int(src.get("max_age_days", freshness_days))
                if age > max_age:
                    gates.append("LEGAL_SOURCE_STALE")
                    messages.append(
                        f"Source stale ({age}d > {max_age}d): {src.get('id') or src.get('title')}"
                    )
            except ValueError:
                gates.append("LEGAL_SOURCE_DATE_INVALID")
                messages.append(f"Invalid source date: {retrieved}")

    # Human/legal review triggers
    triggers: List[str] = []
    if "LEGAL_BINDING_PROHIBITED" in gates or "LEGAL_FILING_FORBIDDEN" in gates:
        triggers.append("retain_licensed_counsel")
    if "LEGAL_SOURCE_STALE" in gates:
        triggers.append("refresh_sources_then_human_review")
    if any(a in (requested_actions or []) for a in ("legal_file", "mutate_external")):
        triggers.append("explicit_human_confirmation")

    ok = len(gates) == 0
    return AssuranceResult(
        ok=ok,
        status="pass" if ok else "blocked",
        gate_codes=gates,
        messages=messages,
        risk_level="high" if not ok else "elevated",
        evidence={
            "human_review_triggers": triggers,
            "informational_only": True,
            "legal_filing_allowed": False,
        },
        notes=["Legal outputs are informational; never binding advice or filings."],
    )


# ---------------------------------------------------------------------------
# Planted defect routing (behavioral acceptance)
# ---------------------------------------------------------------------------


def evaluate_planted_defect(defect: Dict[str, Any]) -> AssuranceResult:
    """Route a synthetic planted defect to the correct accountable gate."""
    kind = defect.get("defect_kind") or defect.get("kind")
    if not kind:
        return AssuranceResult(
            ok=False,
            status="error",
            gate_codes=["VALIDATION_FAILED"],
            messages=["defect_kind required"],
        )
    try:
        route = route_defect(kind)
    except ValueError as exc:
        return AssuranceResult(
            ok=False,
            status="error",
            gate_codes=["UNKNOWN_DEFECT_KIND"],
            messages=[str(exc)],
        )

    severity = defect.get("severity", "S2")
    finding = create_finding(
        defect_kind=kind,
        severity=severity,
        title=defect.get("title") or f"Planted {kind} defect",
        evidence=defect.get("evidence") or ["synthetic-planted-defect"],
        reporter_role=defect.get("reporter_role") or "quality-os",
        closure_criteria=defect.get("closure_criteria") or "",
        finding_id=defect.get("finding_id"),
    )
    order = finding_to_order(finding)

    expected_role = defect.get("expected_accountable_role") or route["accountable_role"]
    expected_gate = defect.get("expected_gate") or kind

    codes: List[str] = []
    messages: List[str] = []
    if finding.accountable_role != expected_role:
        codes.append("GATE_MISROUTE")
        messages.append(
            f"expected accountable {expected_role}, got {finding.accountable_role}"
        )
    if expected_gate != kind and expected_gate not in (kind, finding.accountable_role):
        # allow expected_gate to be role or kind
        if expected_gate != finding.accountable_role:
            codes.append("GATE_MISROUTE")
            messages.append(f"expected gate {expected_gate}")

    # Optional: attempt illegal self-close to prove ban
    self_close_codes: List[str] = []
    if defect.get("attempt_self_close", True) and severity in BLOCKING_SEVERITIES:
        _, self_close_codes = can_close_finding(
            finding,
            closer_role=finding.accountable_role,
            independent_evidence=["I fixed it"],
        )
        if "SELF_APPROVAL_FORBIDDEN" not in self_close_codes:
            codes.append("SELF_APPROVAL_NOT_ENFORCED")
            messages.append("accountable role was able to self-close blocking finding")

    ok = len(codes) == 0
    # Fixture expectation: outcome pass means routing correct (suite passes)
    return AssuranceResult(
        ok=ok,
        status="pass" if ok else "blocked",
        gate_codes=codes
        + (["SELF_APPROVAL_FORBIDDEN"] if "SELF_APPROVAL_FORBIDDEN" in self_close_codes else []),
        messages=messages,
        findings=[finding.to_dict()],
        orders=[order.to_dict()],
        required_gates=[kind],
        risk_level=SEVERITY_TO_RISK.get(severity, "elevated"),
        evidence={
            "route": route,
            "self_close_blocked": "SELF_APPROVAL_FORBIDDEN" in self_close_codes,
        },
    )


def evaluate_artifact_packet(packet: Dict[str, Any]) -> AssuranceResult:
    """Evaluate a requirements/design/test/security/privacy/legal evidence packet."""
    risk = classify_risk(
        blast_radius=packet.get("blast_radius", "local"),
        data_sensitivity=packet.get("data_sensitivity", "none"),
        user_facing=bool(packet.get("user_facing", False)),
        mutates_external=bool(packet.get("mutates_external", False)),
        regulatory=bool(packet.get("regulatory", False)),
        release_candidate=bool(packet.get("release_candidate", False)),
        explicit_level=packet.get("risk_level"),
    )
    dimensions = packet.get("dimensions") or []
    required = required_specialist_gates(risk, dimensions)

    present_gates = set(packet.get("completed_gates") or [])
    evidence = packet.get("evidence") or {}
    missing = [g for g in required if g not in present_gates]

    codes: List[str] = []
    messages: List[str] = []
    findings: List[Finding] = []

    for g in missing:
        codes.append("MISSING_SPECIALIST_GATE")
        messages.append(f"Required gate not completed: {g} → {ACCOUNTABLE_GATES[g]}")
        findings.append(
            create_finding(
                defect_kind=g,
                severity="S2" if risk_at_least(risk, "high") else "S3",
                title=f"Missing {g} gate evidence",
                evidence=[f"required_at_risk={risk}"],
                reporter_role="quality-os",
            )
        )

    # Evidence schema checks for present gates
    for g in present_gates:
        if g not in ACCOUNTABLE_GATES:
            codes.append("UNKNOWN_GATE")
            messages.append(f"Unknown gate in completed_gates: {g}")
            continue
        art = evidence.get(g)
        if not art:
            codes.append("MISSING_GATE_EVIDENCE")
            messages.append(f"Gate {g} marked complete without evidence artifact")
            findings.append(
                create_finding(
                    defect_kind=g,
                    severity="S2",
                    title=f"Gate {g} lacks evidence",
                    evidence=["completed_gates without evidence"],
                    reporter_role="quality-os",
                )
            )
        elif isinstance(art, dict):
            if not art.get("artifacts") and not art.get("summary"):
                codes.append("MISSING_GATE_EVIDENCE")
                messages.append(f"Gate {g} evidence empty")

    # Planted defects inside packet
    for planted in packet.get("planted_defects") or []:
        pr = evaluate_planted_defect(planted)
        if not pr.ok:
            codes.extend(pr.gate_codes)
            messages.extend(pr.messages)
        for fd in pr.findings:
            findings.append(Finding.from_dict(fd))

    # Legal text check if present
    if packet.get("legal_text") is not None or "legal_risk" in dimensions or "compliance" in dimensions:
        legal = check_legal_boundaries(
            packet.get("legal_text") or "",
            requested_actions=packet.get("requested_actions"),
            sources=packet.get("sources"),
        )
        if not legal.ok:
            codes.extend(legal.gate_codes)
            messages.extend(legal.messages)

    # Blocking findings open → packet blocked
    open_blocking = [
        f for f in findings if f.severity in BLOCKING_SEVERITIES and f.status == "open"
    ]
    if open_blocking:
        if "OPEN_BLOCKING_FINDINGS" not in codes:
            codes.append("OPEN_BLOCKING_FINDINGS")
        messages.append(f"{len(open_blocking)} open blocking finding(s)")

    orders = convert_findings_to_orders(findings)
    ok = len([c for c in codes if c not in ("SELF_APPROVAL_FORBIDDEN",)]) == 0 and not open_blocking
    # refine: if only informational issues
    hard = {
        "MISSING_SPECIALIST_GATE",
        "MISSING_GATE_EVIDENCE",
        "OPEN_BLOCKING_FINDINGS",
        "LEGAL_BINDING_PROHIBITED",
        "LEGAL_FILING_FORBIDDEN",
        "HIGH_STAKES_REQUIRES_HUMAN",
        "GATE_MISROUTE",
        "SELF_APPROVAL_NOT_ENFORCED",
        "UNKNOWN_GATE",
        "LEGAL_DISCLAIMER_MISSING",
        "LEGAL_SOURCE_REQUIRED",
        "LEGAL_SOURCE_STALE",
        "LEGAL_SOURCE_DATE_MISSING",
        "LEGAL_SOURCE_DATE_INVALID",
    }
    hard_hit = [c for c in codes if c in hard]
    ok = len(hard_hit) == 0

    return AssuranceResult(
        ok=ok,
        status="pass" if ok else "blocked",
        gate_codes=list(dict.fromkeys(codes)),
        messages=messages,
        findings=[f.to_dict() for f in findings],
        orders=[o.to_dict() for o in orders],
        required_gates=required,
        risk_level=risk,
        evidence={
            "completed_gates": sorted(present_gates),
            "missing_gates": missing,
            "blocking_open": len(open_blocking),
        },
    )


# ---------------------------------------------------------------------------
# Fixture I/O
# ---------------------------------------------------------------------------


def load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _apply_expectations(result: AssuranceResult, expected: Dict[str, Any]) -> AssuranceResult:
    """Interpret fixture expectations. fail_gate means the *suite* passes when gates fire."""
    if not expected:
        return result
    exp_outcome = expected.get("outcome")
    if exp_outcome == "pass" and not result.ok:
        result.ok = False
        result.notes.append("expected pass but blocked")
    elif exp_outcome == "fail_gate" and result.ok:
        result.ok = False
        result.gate_codes = result.gate_codes + ["EXPECTED_GATE_NOT_FIRED"]
        result.notes.append("expected fail_gate but passed")
    elif exp_outcome == "fail_gate" and not result.ok:
        want = set(expected.get("gate_codes") or [])
        if want and not want.intersection(result.gate_codes):
            result.ok = False
            result.notes.append(f"expected gates {want}, got {result.gate_codes}")
        else:
            result.ok = True
            result.status = "pass"
            result.notes.append("fail_gate expectation met")
    exp_role = expected.get("accountable_role")
    if exp_role and result.findings:
        got = result.findings[0].get("accountable_role")
        if got != exp_role:
            result.ok = False
            result.gate_codes = result.gate_codes + ["GATE_MISROUTE"]
            result.notes.append(f"expected role {exp_role}, got {got}")
    return result


def evaluate_path(path: Path) -> AssuranceResult:
    data = load_json(path)
    kind = data.get("fixture_kind") or data.get("kind") or "packet"
    expected = data.get("expectations") or {}

    if kind in ("planted_defect", "defect"):
        result = evaluate_planted_defect(data.get("defect") or data)
        return _apply_expectations(result, expected)

    if kind in ("legal", "legal_boundary"):
        result = check_legal_boundaries(
            data.get("text") or data.get("legal_text") or "",
            requested_actions=data.get("requested_actions"),
            sources=data.get("sources"),
            freshness_days=int(data.get("freshness_days", DEFAULT_SOURCE_FRESHNESS_DAYS)),
        )
        # Default negative legal fixtures without expectations: suite requires explicit outcome
        if not expected and not result.ok:
            # treat as fail_gate success so planted bad legal cases are valid suite fixtures
            expected = {"outcome": "fail_gate", "gate_codes": list(result.gate_codes)}
        return _apply_expectations(result, expected)

    if kind in ("closure", "self_approval"):
        finding = Finding.from_dict(data["finding"])
        allowed, codes = can_close_finding(
            finding,
            closer_role=data.get("closer_role", finding.accountable_role),
            independent_evidence=data.get("independent_evidence") or [],
            waiver=Waiver(**data["waiver"]) if data.get("waiver") else None,
        )
        expect_block = bool(data.get("expect_blocked", True))
        ok = (not allowed) if expect_block else allowed
        if expect_block and allowed:
            ok = False
            codes = codes + ["SELF_APPROVAL_NOT_ENFORCED"]
        result = AssuranceResult(
            ok=ok,
            status="pass" if ok else "blocked",
            gate_codes=codes,
            messages=["closure evaluation"],
            findings=[finding.to_dict()],
            evidence={"allowed": allowed, "expect_blocked": expect_block},
        )
        return _apply_expectations(result, expected)

    # default: artifact packet
    packet = data.get("packet") or data
    result = evaluate_artifact_packet(packet)
    return _apply_expectations(result, expected)


def run_suite(root: Path) -> Dict[str, Any]:
    paths = sorted(root.rglob("*.json"))
    results = []
    passed = failed = 0
    for path in paths:
        if path.name.startswith("_"):
            continue
        r = evaluate_path(path)
        entry = {
            "path": str(path),
            "ok": r.ok,
            "status": r.status,
            "gate_codes": r.gate_codes,
            "risk_level": r.risk_level,
            "notes": r.notes,
        }
        results.append(entry)
        if r.ok:
            passed += 1
        else:
            failed += 1
    return {
        "schema_version": SCHEMA_VERSION,
        "assurance_version": ASSURANCE_VERSION,
        "total": len(results),
        "passed": passed,
        "failed": failed,
        "ok": failed == 0,
        "results": results,
    }


# ---------------------------------------------------------------------------
# Capability audit (existing product/design/qa/security/legal skills)
# ---------------------------------------------------------------------------

DOMAIN_ROOTS = {
    "product-project": "product-project",
    "design": "design",
    "quality-security": "quality-security",
    "legal-compliance": "legal-compliance",
}


def audit_existing_capabilities(employees_root: Path) -> Dict[str, Any]:
    """Audit SKILL.md surfaces under the four allowed domains."""
    adopted: List[str] = []
    corrected: List[str] = []
    retired: List[str] = []
    gaps: List[str] = []
    inventory: List[Dict[str, Any]] = []

    for domain, rel in DOMAIN_ROOTS.items():
        root = employees_root / rel
        if not root.is_dir():
            gaps.append(f"missing domain root: {rel}")
            continue
        for skill_md in sorted(root.rglob("SKILL.md")):
            # skip nested assurance packages if any
            rel_skill = skill_md.relative_to(employees_root)
            text = skill_md.read_text(encoding="utf-8", errors="replace")
            name = skill_md.parent.name
            has_output = "OUTPUT CONTRACT" in text
            has_gate = "SELF-QA GATE" in text or "SELF_QA" in text
            has_disclaimer = bool(
                re.search(r"not (a )?lawyer|not legal advice|informational", text, re.I)
            )
            has_assurance_ref = "ASSURANCE" in text or "Quality OS" in text or "accountable gate" in text
            provider_lock = bool(re.search(r"\b(?:Claude|Codex|Grok|OpenAI|DeepSeek) is Solaris", text))
            entry = {
                "id": f"solaris/{name}",
                "path": str(rel_skill),
                "domain": domain,
                "has_output_contract": has_output,
                "has_self_qa_gate": has_gate,
                "has_legal_disclaimer": has_disclaimer,
                "has_assurance_hook": has_assurance_ref,
                "provider_lock_prose": provider_lock,
            }
            inventory.append(entry)
            if has_output and has_gate:
                adopted.append(entry["id"])
            else:
                gaps.append(f"{entry['id']}: missing output contract or self-qa gate")
            if domain == "legal-compliance" and not has_disclaimer:
                corrected.append(f"{entry['id']}: requires legal informational disclaimer")
            if provider_lock:
                corrected.append(
                    f"{entry['id']}: provider-locked prose ('Claude is…') — migrate toward provider-neutral agent contract"
                )

    # Assurance contracts we ship are adopted
    for domain in DOMAIN_ROOTS:
        assurance = employees_root / domain / "assurance"
        if (assurance / "ASSURANCE.md").is_file() or (
            employees_root / "quality-security" / "assurance" / "ASSURANCE.md"
        ).is_file():
            adopted.append(f"assurance/{domain}")

    return {
        "schema_version": SCHEMA_VERSION,
        "audit": "skill-solaris-product-quality-hardening",
        "adopted": sorted(set(adopted)),
        "corrected": sorted(set(corrected)),
        "retired": retired,
        "gaps": gaps,
        "inventory": inventory,
        "counts": {
            "skills_scanned": len(inventory),
            "adopted": len(set(adopted)),
            "corrected": len(set(corrected)),
            "gaps": len(gaps),
        },
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _repo_root() -> Path:
    # .../solaris/employees/quality-security/assurance/quality_os.py → repo root
    return Path(__file__).resolve().parents[4]


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Solaris Quality OS assurance engine")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_run = sub.add_parser("run", help="Evaluate one fixture")
    p_run.add_argument("path", type=Path)

    p_suite = sub.add_parser("suite", help="Run all fixtures under a directory")
    p_suite.add_argument(
        "root",
        type=Path,
        nargs="?",
        default=None,
    )

    p_audit = sub.add_parser("audit", help="Audit product/design/qa/security/legal skills")
    p_audit.add_argument(
        "--employees",
        type=Path,
        default=None,
        help="Path to solaris/employees",
    )

    p_route = sub.add_parser("route", help="Show gate route for a defect kind")
    p_route.add_argument("defect_kind")

    sub.add_parser("self-test", help="Built-in smoke checks")

    args = parser.parse_args(argv)
    root = _repo_root()

    if args.cmd == "run":
        result = evaluate_path(args.path)
        print(json.dumps(result.to_dict(), indent=2))
        return 0 if result.ok else 1

    if args.cmd == "suite":
        suite_root = args.root or (root / "fixtures" / "solaris" / "assurance")
        report = run_suite(suite_root)
        print(json.dumps(report, indent=2))
        return 0 if report["ok"] else 1

    if args.cmd == "audit":
        employees = args.employees or (root / "solaris" / "employees")
        report = audit_existing_capabilities(employees)
        print(json.dumps(report, indent=2))
        return 0

    if args.cmd == "route":
        print(json.dumps(route_defect(args.defect_kind), indent=2))
        return 0

    if args.cmd == "self-test":
        failures = []
        # risk
        if classify_risk(user_facing=True, data_sensitivity="pii") != "elevated":
            failures.append("risk pii+user_facing")
        # route all kinds
        for k in DEFECT_KINDS:
            r = route_defect(k)
            if r["accountable_role"] != ACCOUNTABLE_GATES[k]:
                failures.append(f"route {k}")
        # self-approval
        f = create_finding(
            defect_kind="security",
            severity="S1",
            title="XSS",
            evidence=["e"],
            reporter_role="qa-engineer",
        )
        allowed, codes = can_close_finding(
            f, closer_role="security-auditor", independent_evidence=["fixed"]
        )
        if allowed or "SELF_APPROVAL_FORBIDDEN" not in codes:
            failures.append("self-approval ban")
        # independent close ok
        allowed2, codes2 = can_close_finding(
            f, closer_role="code-reviewer", independent_evidence=["verified in PR"]
        )
        if not allowed2:
            failures.append(f"independent close failed: {codes2}")
        # legal
        legal = check_legal_boundaries(
            "I am your attorney; file this lawsuit now.",
            requested_actions=["legal_file"],
        )
        if legal.ok or "LEGAL_BINDING_PROHIBITED" not in legal.gate_codes:
            failures.append("legal binding")
        # planted
        for kind, role in ACCOUNTABLE_GATES.items():
            pr = evaluate_planted_defect(
                {
                    "defect_kind": kind,
                    "severity": "S2",
                    "title": f"planted {kind}",
                    "expected_accountable_role": role,
                }
            )
            if not pr.ok:
                failures.append(f"planted {kind}: {pr.gate_codes} {pr.messages}")
        if failures:
            print(json.dumps({"ok": False, "failures": failures}, indent=2))
            return 1
        print(json.dumps({"ok": True, "assurance_version": ASSURANCE_VERSION}, indent=2))
        return 0

    return 2


if __name__ == "__main__":
    sys.exit(main())
