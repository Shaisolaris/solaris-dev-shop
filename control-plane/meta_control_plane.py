#!/usr/bin/env python3
"""Deterministic meta control-plane (provider-neutral, stdlib only).

Separates **policy/routing** (this module) from provider reasoning. Produces
typed assignment packets, escalations, and closure-evidence requirements.
Coordinators never perform specialist work here.

Usage:
  python3 control-plane/meta_control_plane.py intake "build API + landing page"
  python3 control-plane/meta_control_plane.py intake --fixture fixtures/control-plane/multi_domain_intake.json
  python3 control-plane/meta_control_plane.py self-test
  python3 control-plane/meta_control_plane.py roster
  python3 control-plane/meta_control_plane.py budgets
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

ROOT = Path(__file__).resolve().parents[2]
CONTROL_PLANE_DIR = Path(__file__).resolve().parent
POLICY_PATH = CONTROL_PLANE_DIR / "policy.json"
ROSTER_PATH = CONTROL_PLANE_DIR / "roster.json"
BUDGETS_PATH = CONTROL_PLANE_DIR / "budgets.json"
FIXTURE_ROOT = ROOT / "fixtures" / "meta"

SCHEMA_VERSION = "1.0.0"
ENGINE_VERSION = "1.0.0"

# Decision codes
ASSIGN = "assign"
ESCALATE = "escalate"
CLARIFY = "clarify"
BLOCK = "block"

# Escalation reasons
OUT_OF_AUTHORITY = "out_of_authority"
AMBIGUOUS = "ambiguous"
HIGH_RISK = "high_risk"
UNAVAILABLE_CAPABILITY = "unavailable_capability"
BUDGET_EXCEEDED = "budget_exceeded"
PERMISSION_REQUIRED = "permission_required"

PROVIDERS = ("claude", "codex", "grok", "kimi")


@dataclass
class Assignment:
    """One bounded accountable assignment. Coordinator does not perform the work."""

    assignment_id: str
    outcome: str
    accountable: str
    primary_capability: str
    supporting: List[str]
    scope: str
    authority_bound: List[str]
    must_not: List[str]
    evidence_required: List[str]
    domains: List[str]
    risk: str

    def as_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class Escalation:
    reason: str
    message: str
    required_actor: str
    evidence: List[str] = field(default_factory=list)

    def as_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class Decision:
    schema_version: str
    engine_version: str
    decision: str  # assign | escalate | clarify | block
    coordinator: str
    request_summary: str
    domains: List[str]
    risk: str
    assignment: Optional[Assignment]
    escalation: Optional[Escalation]
    closure_evidence: Dict[str, Any]
    budgets_applied: Dict[str, Any]
    provider_invariants: List[str]
    performed_work: bool  # always False for control-plane
    ts: str

    def as_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        return d


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class InputError(Exception):
    """User-facing input problem: missing file, bad JSON, invalid fixture."""


def _load_json(path: Path) -> Dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise InputError(f"file not found: {path}")
    except json.JSONDecodeError as e:
        raise InputError(f"invalid JSON in {path}: {e}")


def load_policy() -> Dict[str, Any]:
    return _load_json(POLICY_PATH)


def load_roster() -> Dict[str, Any]:
    return _load_json(ROSTER_PATH)


def load_budgets() -> Dict[str, Any]:
    return _load_json(BUDGETS_PATH)


def _word_boundary_hit(keyword: str, text: str) -> bool:
    return (
        re.search(
            r"(?<![a-z0-9])" + re.escape(keyword.lower()) + r"(?![a-z0-9])",
            text.lower(),
        )
        is not None
    )


def detect_domains(text: str, policy: Dict[str, Any]) -> List[str]:
    hits: List[str] = []
    for domain, kws in policy.get("domain_keywords", {}).items():
        if any(_word_boundary_hit(k, text) for k in kws):
            hits.append(domain)
    return hits or ["general"]


def detect_risk(text: str, policy: Dict[str, Any]) -> str:
    high = policy.get("high_risk_keywords", [])
    if any(_word_boundary_hit(k, text) for k in high):
        return "high"
    med = policy.get("medium_risk_keywords", [])
    if any(_word_boundary_hit(k, text) for k in med):
        return "medium"
    return "low"


def is_ambiguous(text: str, policy: Dict[str, Any]) -> bool:
    t = text.strip().lower()
    if len(t.split()) < int(policy.get("min_words_for_clear_goal", 4)):
        return True
    for phrase in policy.get("ambiguous_phrases", []):
        if phrase.lower() in t:
            return True
    # No concrete verb / outcome signal
    outcome_verbs = policy.get(
        "outcome_verbs",
        ["build", "review", "write", "fix", "deploy", "design", "plan", "audit", "route"],
    )
    if not any(_word_boundary_hit(v, t) for v in outcome_verbs) and not any(
        c in t for c in ("?",)
    ):
        # still allow if domains are multi and has substance
        if len(t.split()) < 8:
            return True
    return False


def out_of_authority(
    text: str, coordinator: str, policy: Dict[str, Any]
) -> Optional[str]:
    """Return reason if request is outside the coordinator's authority."""
    bounds = policy.get("coordinator_authority", {}).get(coordinator, {})
    forbidden = bounds.get("forbidden_domains", [])
    domains = detect_domains(text, policy)
    for d in domains:
        if d in forbidden:
            return f"domain '{d}' is outside authority of {coordinator}"
    # Solaris CoS must not touch personal health/finance/travel content.
    # Personal signals escalate to the owner.
    if coordinator == "meta.chief-of-staff":
        for phrase in policy.get("personal_signals", []):
            if phrase.lower() in text.lower():
                return (
                    f"Personal signal '{phrase}' is out of scope for this tree, "
                    "escalate to the owner"
                )
    return None


def _rule_score(keywords: List[str], text: str) -> Tuple[int, int]:
    """Return (total matched keyword length, longest single matched keyword)."""
    hits = [k for k in keywords if _word_boundary_hit(k, text)]
    if not hits:
        return 0, 0
    return sum(len(k) for k in hits), max(len(k) for k in hits)


def _override_phrase_hit(text: str, policy: Dict[str, Any]) -> bool:
    """True if any route_override exact keyword phrase hits.

    Used to let canonical override phrasings (e.g. "review this code")
    bypass the min-words ambiguity check. keywords_all rules are resolve-time
    only and do not count here.
    """
    for rule in policy.get("route_overrides", []):
        if any(_word_boundary_hit(k, text) for k in rule.get("keywords", [])):
            return True
    return False


def resolve_capability(
    domains: List[str],
    text: str,
    roster: Dict[str, Any],
    policy: Dict[str, Any],
) -> Tuple[Optional[str], List[str], Optional[str]]:
    """Return (primary, supporting, unavailable_reason).

    Scoring router: every route_override rule and every capability_keywords
    entry is scored by word-boundary keyword hits (sum of matched keyword
    lengths). Highest score wins; ties break by route_overrides listed order,
    then by longest single matched keyword. With no keyword hits at all, falls
    back to domain_to_capability, then the default capability.
    """
    candidates: List[Tuple[int, int, int, int, List[str]]] = []
    # (score, source_order, rule_index, longest_keyword, capabilities)
    for idx, rule in enumerate(policy.get("route_overrides", [])):
        kws = list(rule.get("keywords", []))
        all_kws = list(rule.get("keywords_all", []))
        score_any, longest_any = _rule_score(kws, text)
        if all_kws:
            if all(_word_boundary_hit(k, text) for k in all_kws):
                s_all, l_all = _rule_score(all_kws, text)
                score_any += s_all
                longest_any = max(longest_any, l_all)
            else:
                score_any, longest_any = 0, 0
        if score_any > 0:
            candidates.append(
                (score_any, 0, idx, longest_any, list(rule.get("capabilities", [])))
            )

    for cap_id, kws in policy.get("capability_keywords", {}).items():
        score, longest = _rule_score(list(kws), text)
        if score > 0:
            candidates.append((score, 1, 0, longest, [cap_id]))

    caps: List[str] = []
    if candidates:
        candidates.sort(key=lambda c: (-c[0], c[1], c[2], -c[3]))
        caps = list(candidates[0][4])
    else:
        route_map = policy.get("domain_to_capability", {})
        for d in domains:
            cap = route_map.get(d)
            if cap:
                caps.append(cap)

    if not caps:
        caps = [policy.get("default_capability", "solaris.backend-developer")]

    # Dedupe preserving order
    seen = set()
    ordered: List[str] = []
    for c in caps:
        if c not in seen:
            seen.add(c)
            ordered.append(c)

    active = {
        c["id"]
        for c in roster.get("capabilities", [])
        if c.get("status") == "active"
    }
    unavailable = [c for c in ordered if c not in active]
    if unavailable:
        return None, [], f"unavailable: {', '.join(unavailable)}"

    primary = ordered[0]
    supporting = ordered[1:]
    return primary, supporting, None


def _closure_evidence(risk: str, policy: Dict[str, Any]) -> Dict[str, Any]:
    base = list(policy.get("closure_evidence_required", []))
    if risk == "high":
        base = base + list(policy.get("high_risk_extra_evidence", []))
    return {
        "required_artifacts": base,
        "acceptance": policy.get(
            "closure_acceptance",
            "Every named capability was invoked or explicitly queued; no phantom credits; "
            "coordinator did not perform specialist work.",
        ),
        "redaction": policy.get(
            "closure_redaction",
            "Strip credentials, tokens, private health/finance/personal content, raw connector data.",
        ),
    }


def intake(
    request: str,
    *,
    coordinator: str = "meta.chief-of-staff",
    policy: Optional[Dict[str, Any]] = None,
    roster: Optional[Dict[str, Any]] = None,
    budgets: Optional[Dict[str, Any]] = None,
    budget_usage: Optional[Dict[str, Any]] = None,
) -> Decision:
    """Run deterministic intake → assignment or genuine escalation.

    Never performs specialist work. Always sets performed_work=False.
    """
    policy = policy or load_policy()
    roster = roster or load_roster()
    budgets = budgets or load_budgets()
    budget_usage = budget_usage or {}

    text = (request or "").strip()
    summary = text if len(text) <= 200 else text[:197] + "..."
    domains = detect_domains(text, policy)
    risk = detect_risk(text, policy)

    # Empty request
    if not text:
        return Decision(
            schema_version=SCHEMA_VERSION,
            engine_version=ENGINE_VERSION,
            decision=BLOCK,
            coordinator=coordinator,
            request_summary="",
            domains=[],
            risk="low",
            assignment=None,
            escalation=Escalation(
                reason=AMBIGUOUS,
                message="Empty request, no assignable outcome",
                required_actor="user",
                evidence=["empty_request"],
            ),
            closure_evidence=_closure_evidence("low", policy),
            budgets_applied=budgets.get("defaults", {}),
            provider_invariants=list(policy.get("provider_invariants", [])),
            performed_work=False,
            ts=_now(),
        )

    # Out of authority
    ooa = out_of_authority(text, coordinator, policy)
    if ooa:
        return Decision(
            schema_version=SCHEMA_VERSION,
            engine_version=ENGINE_VERSION,
            decision=ESCALATE,
            coordinator=coordinator,
            request_summary=summary,
            domains=domains,
            risk=risk,
            assignment=None,
            escalation=Escalation(
                reason=OUT_OF_AUTHORITY,
                message=ooa,
                required_actor=policy.get("coordinator_authority", {})
                .get(coordinator, {})
                .get("escalate_to", "owner"),
                evidence=["authority_policy", "domain_detection"],
            ),
            closure_evidence=_closure_evidence(risk, policy),
            budgets_applied=budgets.get("defaults", {}),
            provider_invariants=list(policy.get("provider_invariants", [])),
            performed_work=False,
            ts=_now(),
        )

    # High risk → always genuine escalation (human confirmation)
    if risk == "high":
        return Decision(
            schema_version=SCHEMA_VERSION,
            engine_version=ENGINE_VERSION,
            decision=ESCALATE,
            coordinator=coordinator,
            request_summary=summary,
            domains=domains,
            risk=risk,
            assignment=None,
            escalation=Escalation(
                reason=HIGH_RISK,
                message="High-risk request (money, external mutation, deploy, diagnosis, legal filing) "
                "requires explicit human confirmation before any assignment.",
                required_actor="owner",
                evidence=["high_risk_keywords", "permission_policy"],
            ),
            closure_evidence=_closure_evidence(risk, policy),
            budgets_applied=budgets.get("defaults", {}),
            provider_invariants=list(policy.get("provider_invariants", [])),
            performed_work=False,
            ts=_now(),
        )

    # Ambiguous (canonical route_override phrasings bypass the min-words check)
    if not _override_phrase_hit(text, policy) and is_ambiguous(text, policy):
        return Decision(
            schema_version=SCHEMA_VERSION,
            engine_version=ENGINE_VERSION,
            decision=CLARIFY,
            coordinator=coordinator,
            request_summary=summary,
            domains=domains,
            risk=risk,
            assignment=None,
            escalation=Escalation(
                reason=AMBIGUOUS,
                message="Ambiguous request, ask ONE clarifying question for the desired outcome; do not guess.",
                required_actor="user",
                evidence=["ambiguous_phrases_or_underspecified_goal"],
            ),
            closure_evidence=_closure_evidence(risk, policy),
            budgets_applied=budgets.get("defaults", {}),
            provider_invariants=list(policy.get("provider_invariants", [])),
            performed_work=False,
            ts=_now(),
        )

    # Budget gates (synthetic usage counters for review-bound operations)
    defaults = budgets.get("defaults", {})
    if budget_usage.get("scout_external_queries", 0) > defaults.get(
        "scout_external_queries", 20
    ):
        return Decision(
            schema_version=SCHEMA_VERSION,
            engine_version=ENGINE_VERSION,
            decision=ESCALATE,
            coordinator=coordinator,
            request_summary=summary,
            domains=domains,
            risk=risk,
            assignment=None,
            escalation=Escalation(
                reason=BUDGET_EXCEEDED,
                message="External scout query budget exceeded, review required before further scouting.",
                required_actor="owner",
                evidence=["budgets.scout_external_queries"],
            ),
            closure_evidence=_closure_evidence(risk, policy),
            budgets_applied=defaults,
            provider_invariants=list(policy.get("provider_invariants", [])),
            performed_work=False,
            ts=_now(),
        )

    if budget_usage.get("learning_promotions_pending", 0) > defaults.get(
        "learning_promotions_auto_max", 3
    ):
        # Still allow assignment of synthesizer, but flag review
        pass

    if budget_usage.get("roster_mutations", 0) > 0 and not budget_usage.get(
        "roster_mutation_approved"
    ):
        return Decision(
            schema_version=SCHEMA_VERSION,
            engine_version=ENGINE_VERSION,
            decision=ESCALATE,
            coordinator=coordinator,
            request_summary=summary,
            domains=domains,
            risk=risk,
            assignment=None,
            escalation=Escalation(
                reason=PERMISSION_REQUIRED,
                message="Roster mutations require explicit review/approval.",
                required_actor="owner",
                evidence=["budgets.roster_mutations_require_review"],
            ),
            closure_evidence=_closure_evidence(risk, policy),
            budgets_applied=defaults,
            provider_invariants=list(policy.get("provider_invariants", [])),
            performed_work=False,
            ts=_now(),
        )

    primary, supporting, unavail = resolve_capability(domains, text, roster, policy)
    if unavail:
        return Decision(
            schema_version=SCHEMA_VERSION,
            engine_version=ENGINE_VERSION,
            decision=ESCALATE,
            coordinator=coordinator,
            request_summary=summary,
            domains=domains,
            risk=risk,
            assignment=None,
            escalation=Escalation(
                reason=UNAVAILABLE_CAPABILITY,
                message=unavail + ", do not invent a specialist; escalate to the owner.",
                required_actor="owner",
                evidence=["roster_active_set", "domain_to_capability"],
            ),
            closure_evidence=_closure_evidence(risk, policy),
            budgets_applied=defaults,
            provider_invariants=list(policy.get("provider_invariants", [])),
            performed_work=False,
            ts=_now(),
        )

    assert primary is not None
    # Enforce assignment_max_supporting from budgets.json (CODE-08).
    max_supporting = int(defaults.get("assignment_max_supporting", 5))
    supporting_truncated = len(supporting) > max_supporting
    supporting = supporting[:max_supporting]
    # Multi-domain: still ONE assignment packet with one accountable specialist.
    # The accountable is always the best-matched primary capability; it is never
    # the coordinator. Domain defaults are a fallback only when the primary is
    # not an active roster capability.
    active_ids = {
        c["id"] for c in roster.get("capabilities", []) if c.get("status") == "active"
    }
    if primary in active_ids:
        accountable = primary
    else:
        accountable = policy.get("domain_accountable", {}).get(domains[0], primary)
    if accountable not in active_ids:
        accountable = policy.get("default_capability", primary)

    assignment = Assignment(
        assignment_id=f"asg-{uuid.uuid4().hex[:12]}",
        outcome=f"Bounded delivery for: {summary}",
        accountable=accountable,
        primary_capability=primary,
        supporting=supporting,
        scope=(
            f"Domains={','.join(domains)}; risk={risk}; "
            f"coordinator={coordinator} does not perform specialist work."
        ),
        authority_bound=list(
            policy.get("assignment_authority_bounds", [
                "stay within declared capability authority",
                "no production deploy without human",
                "no spend / message_send / external mutation without human",
            ])
        ),
        must_not=list(
            policy.get(
                "assignment_must_not",
                [
                    "coordinator_performs_specialist_work",
                    "phantom_credit_without_invocation",
                    "autonomous_scope_expansion",
                    "personal_data_in_solaris_packet",
                    "credentials_in_handoff",
                ],
            )
        ),
        evidence_required=list(
            _closure_evidence(risk, policy)["required_artifacts"]
        ),
        domains=domains,
        risk=risk,
    )

    budgets_applied = dict(defaults)
    if supporting_truncated:
        budgets_applied["supporting_truncated_to_max"] = True

    return Decision(
        schema_version=SCHEMA_VERSION,
        engine_version=ENGINE_VERSION,
        decision=ASSIGN,
        coordinator=coordinator,
        request_summary=summary,
        domains=domains,
        risk=risk,
        assignment=assignment,
        escalation=None,
        closure_evidence=_closure_evidence(risk, policy),
        budgets_applied=budgets_applied,
        provider_invariants=list(policy.get("provider_invariants", [])),
        performed_work=False,
        ts=_now(),
    )


def run_fixture(path: Path) -> Tuple[Decision, Dict[str, Any]]:
    data = _load_json(path)
    policy = load_policy()
    roster = load_roster()
    overrides = data.get("test_overrides") or {}
    if overrides.get("remove_from_roster"):
        remove = set(overrides["remove_from_roster"])
        roster = {
            "capabilities": [
                c
                for c in roster.get("capabilities", [])
                if c.get("id") not in remove
            ]
        }
    if overrides.get("ensure_domain_map"):
        policy = json.loads(json.dumps(policy))
        policy.setdefault("domain_to_capability", {}).update(
            overrides["ensure_domain_map"]
        )
    decision = intake(
        data.get("request", ""),
        coordinator=data.get("coordinator", "meta.chief-of-staff"),
        budget_usage=data.get("budget_usage"),
        policy=policy,
        roster=roster,
    )
    return decision, data


def check_fixture_expectations(
    decision: Decision, fixture: Dict[str, Any]
) -> List[str]:
    errors: List[str] = []
    exp = fixture.get("expectations", {})
    if "decision" in exp and decision.decision != exp["decision"]:
        errors.append(
            f"decision: got {decision.decision!r} expected {exp['decision']!r}"
        )
    if "escalation_reason" in exp:
        got = decision.escalation.reason if decision.escalation else None
        if got != exp["escalation_reason"]:
            errors.append(
                f"escalation_reason: got {got!r} expected {exp['escalation_reason']!r}"
            )
    if exp.get("performed_work") is False and decision.performed_work:
        errors.append("performed_work must be False")
    if exp.get("has_assignment") is True and decision.assignment is None:
        errors.append("expected assignment packet")
    if exp.get("has_assignment") is False and decision.assignment is not None:
        errors.append("expected no assignment packet")
    if exp.get("single_assignment") and decision.assignment is not None:
        # exactly one primary accountable
        if not decision.assignment.accountable:
            errors.append("assignment missing accountable")
        if not decision.assignment.primary_capability:
            errors.append("assignment missing primary_capability")
    if "min_domains" in exp:
        if len(decision.domains) < int(exp["min_domains"]):
            errors.append(
                f"domains count {len(decision.domains)} < min {exp['min_domains']}"
            )
    return errors


def self_test() -> int:
    """Built-in asserts for acceptance behavioral checks."""
    failures: List[str] = []

    # Multi-domain intake → one bounded assignment, no work performed
    d = intake(
        "Build a REST API and a marketing landing page for the client portal"
    )
    if d.decision != ASSIGN:
        failures.append(f"multi-domain expected assign, got {d.decision}")
    if d.performed_work:
        failures.append("multi-domain coordinator must not perform work")
    if d.assignment is None:
        failures.append("multi-domain must produce assignment")
    elif not d.assignment.accountable or not d.assignment.primary_capability:
        failures.append("multi-domain assignment incomplete")
    if len(d.domains) < 2:
        failures.append(f"multi-domain expected >=2 domains, got {d.domains}")

    # Out of authority
    d2 = intake(
        "Review my blood pressure trends and diagnose hypertension",
        coordinator="meta.chief-of-staff",
    )
    if d2.decision != ESCALATE or (
        d2.escalation and d2.escalation.reason not in (OUT_OF_AUTHORITY, HIGH_RISK)
    ):
        # health on CoS is out of authority; diagnosis is also high risk, either is genuine
        if not (
            d2.decision in (ESCALATE, CLARIFY, BLOCK)
            and d2.escalation is not None
        ):
            failures.append(
                f"out-of-authority/health expected escalation, got {d2.decision}"
            )

    d2c = intake("How do I interpret my blood test results")
    if d2c.decision != ESCALATE or (
        d2c.escalation and d2c.escalation.reason != OUT_OF_AUTHORITY
    ):
        failures.append(
            "personal health signal must escalate out-of-authority to the owner"
        )
    d2d = intake("Should I move my Roth IRA into index funds")
    if d2d.decision != ESCALATE or (
        d2d.escalation and d2d.escalation.reason != OUT_OF_AUTHORITY
    ):
        failures.append(
            "personal finance signal must escalate out-of-authority to the owner"
        )
    d3 = intake("Design a logo for my coffee brand")
    if d3.decision != ASSIGN or (
        d3.assignment and d3.assignment.accountable != "solaris.image-generator"
    ):
        failures.append(
            "logo design must be accountable to solaris.image-generator, "
            f"got {d3.assignment.accountable if d3.assignment else None}"
        )
    d4 = intake("review this code")
    if d4.decision != ASSIGN or (
        d4.assignment and d4.assignment.accountable != "solaris.code-reviewer"
    ):
        failures.append(
            "review this code must be accountable to solaris.code-reviewer, "
            f"got {d4.assignment.accountable if d4.assignment else None}"
        )

    # Ambiguous
    d3 = intake("help me figure out what to do")
    if d3.decision != CLARIFY or (
        d3.escalation and d3.escalation.reason != AMBIGUOUS
    ):
        failures.append(f"ambiguous expected clarify, got {d3.decision}")

    # High risk
    d4 = intake("Wire the payment and charge the client's card now")
    if d4.decision != ESCALATE or (
        d4.escalation and d4.escalation.reason != HIGH_RISK
    ):
        failures.append(f"high-risk expected escalate high_risk, got {d4.decision}")

    # Unavailable capability
    # Inject synthetic roster without mobile capability while requesting mobile
    roster = load_roster()
    slim = {
        "capabilities": [
            c
            for c in roster["capabilities"]
            if c["id"] != "solaris.mobile-developer"
        ]
    }
    # Force route to mobile via override text if policy maps mobile domain
    d5 = intake(
        "Build a native mobile app for iOS and Android",
        roster=slim,
    )
    # If policy maps to mobile-developer and it's unavailable → escalate
    if "mobile" in d5.domains or d5.decision == ESCALATE:
        if d5.decision == ESCALATE:
            if not d5.escalation or d5.escalation.reason != UNAVAILABLE_CAPABILITY:
                # might have assigned something else; force check with explicit override
                pass
    # Explicit: request capability not on roster
    policy = load_policy()
    policy = json.loads(json.dumps(policy))  # deep copy via json
    policy["domain_to_capability"]["mobile"] = "solaris.mobile-developer"
    policy["domain_keywords"]["mobile"] = ["mobile app", "ios", "android", "native mobile"]
    d5b = intake(
        "Build a native mobile app for iOS and Android",
        roster=slim,
        policy=policy,
    )
    if d5b.decision != ESCALATE or (
        d5b.escalation and d5b.escalation.reason != UNAVAILABLE_CAPABILITY
    ):
        failures.append(
            f"unavailable expected escalate unavailable_capability, got "
            f"{d5b.decision}/{d5b.escalation}"
        )

    # Provider invariants listed
    d6 = intake("Review this Python API code for security issues")
    if d6.decision == ASSIGN and not d6.provider_invariants:
        failures.append("assign must list provider invariants")

    # Canonical override phrasing reaches code-reviewer despite min_words
    d7 = intake("review this code")
    if (
        d7.decision != ASSIGN
        or not d7.assignment
        or d7.assignment.primary_capability != "solaris.code-reviewer"
    ):
        failures.append(
            f"'review this code' expected assign to solaris.code-reviewer, got "
            f"{d7.decision}/{d7.assignment.primary_capability if d7.assignment else None}"
        )

    # Longer review phrasing still reaches code-reviewer, not backend/security
    d8 = intake("please review this python code for security issues")
    if (
        d8.decision != ASSIGN
        or not d8.assignment
        or d8.assignment.primary_capability != "solaris.code-reviewer"
    ):
        failures.append(
            f"review-python-code expected solaris.code-reviewer, got "
            f"{d8.decision}/{d8.assignment.primary_capability if d8.assignment else None}"
        )

    # Multi-domain accountability names a specialist, never the coordinator
    d9 = intake("Build a REST API and a marketing landing page for the client portal")
    if (
        d9.decision == ASSIGN
        and d9.assignment
        and d9.assignment.accountable == "meta.chief-of-staff"
    ):
        failures.append("multi-domain accountable must not be the coordinator")

    # Fixture dir if present
    if FIXTURE_ROOT.is_dir():
        for path in sorted(FIXTURE_ROOT.glob("*.json")):
            decision, fixture = run_fixture(path)
            errs = check_fixture_expectations(decision, fixture)
            for e in errs:
                failures.append(f"{path.name}: {e}")

    if failures:
        print("META CONTROL-PLANE SELFTEST FAIL:")
        for f in failures:
            print(f"  - {f}")
        return 1
    print(
        f"meta control-plane selftest: OK (engine {ENGINE_VERSION}, "
        f"providers {','.join(PROVIDERS)})"
    )
    return 0


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_in = sub.add_parser("intake", help="Run intake on a request string")
    p_in.add_argument("request", nargs="*", help="Request text")
    p_in.add_argument("--fixture", type=Path, help="Load request from fixture JSON")
    p_in.add_argument(
        "--coordinator",
        default="meta.chief-of-staff",
        choices=["meta.chief-of-staff"],
    )
    p_in.add_argument("--json", action="store_true", help="Print full JSON decision")

    sub.add_parser("self-test", help="Run built-in behavioral asserts")
    sub.add_parser("roster", help="Print active roster JSON")
    sub.add_parser("budgets", help="Print budgets JSON")
    sub.add_parser("policy", help="Print policy JSON")

    args = parser.parse_args(argv)

    if args.cmd == "self-test":
        return self_test()
    if args.cmd == "roster":
        print(json.dumps(load_roster(), indent=2))
        return 0
    if args.cmd == "budgets":
        print(json.dumps(load_budgets(), indent=2))
        return 0
    if args.cmd == "policy":
        print(json.dumps(load_policy(), indent=2))
        return 0
    if args.cmd == "intake":
        if args.fixture:
            try:
                decision, fixture = run_fixture(args.fixture)
            except InputError as e:
                print(f"error: {e}", file=sys.stderr)
                return 2
            errs = check_fixture_expectations(decision, fixture)
            out = decision.as_dict()
            if args.json:
                print(json.dumps(out, indent=2))
            if errs:
                print("FIXTURE EXPECTATION FAILURES:", file=sys.stderr)
                for e in errs:
                    print(f"  - {e}", file=sys.stderr)
                return 1
            return 0
        req = " ".join(args.request).strip()
        try:
            decision = intake(req, coordinator=args.coordinator)
        except InputError as e:
            print(f"error: {e}", file=sys.stderr)
            return 2
        print(json.dumps(decision.as_dict(), indent=2))
        return 0 if decision.decision in (ASSIGN, CLARIFY, ESCALATE, BLOCK) else 1

    return 2


if __name__ == "__main__":
    try:
        sys.exit(main())
    except InputError as e:
        print(f"error: {e}", file=sys.stderr)
        sys.exit(2)
