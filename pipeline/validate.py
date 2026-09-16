"""
validate.py  -- Stage: Rule-based validation

Takes a raw ResearchRecord as produced by the research/extraction stage and
applies deterministic rules. This stage is intentionally "dumb" (no LLM
calls) so it is 100% reproducible and auditable: the same input JSON always
produces the same flags and corrections.

Two kinds of output:
  1. review_flags   -- appended, never silently dropped, so the reviewer can
                        see exactly why something was flagged.
  2. corrections    -- hard auto-corrections the pipeline is allowed to make
                        (e.g. downgrading an unsupported MCP=OFFICIAL claim).
                        Every correction is logged, never applied silently.

This module does not decide final confidence or human-review routing --
that's confidence.py and review_routing.py, which consume its output.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import List
from .schema import ResearchRecord, Evidence


@dataclass
class ValidationResult:
    flags: List[str] = field(default_factory=list)
    corrections: List[str] = field(default_factory=list)  # human-readable log lines


def _evidence_is_official(ev: Evidence) -> bool:
    return (not ev.is_empty) and ev.source_type == "OFFICIAL"


def _evidence_needs_verification_flag(ev: Evidence) -> bool:
    # Official-by-domain but not actually read (V2, see v1_findings.md #1)
    return (not ev.is_empty) and ev.source_type == "OFFICIAL" and not ev.verified


def _evidence_is_missing(ev: Evidence) -> bool:
    return ev.is_empty


UNCLEAR_LIKE_AUTH = {"UNCLEAR"}
UNCLEAR_LIKE_ACCESS = {"UNCLEAR"}
UNCLEAR_LIKE_API_TYPES = {"UNCLEAR"}
UNCLEAR_LIKE_API_BREADTH = {"UNCLEAR"}

SELF_SERVE_ACCESS = {"SELF_SERVE_FREE", "SELF_SERVE_TRIAL"}
GATED_ACCESS = {"ADMIN_GATED", "PARTNER_GATED", "CONTACT_SALES"}


def validate_record(r: ResearchRecord) -> ValidationResult:
    flags = set(r.review_flags)  # preserve anything the agent/researcher already self-flagged
    corrections: List[str] = []

    # --- 1. Unsupported / missing evidence checks --------------------------
    # A substantive (non-UNCLEAR, non-NONE_FOUND) classification must carry
    # evidence. Empty evidence on a substantive claim is worse than "third
    # party" evidence, but both fail the "official source" bar, so both are
    # covered by NO_OFFICIAL_SOURCE with the specific problem noted below.
    substantive_auth = bool(r.auth_methods) and r.auth_methods != ["NONE_FOUND"] and r.auth_methods != ["UNCLEAR"]
    if substantive_auth:
        if _evidence_is_missing(r.auth_evidence):
            flags.add("NO_OFFICIAL_SOURCE")
            corrections.append("AUTH_METHODS has a substantive value but AUTH_EVIDENCE is empty -> flagged NO_OFFICIAL_SOURCE")
        elif not _evidence_is_official(r.auth_evidence):
            flags.add("NO_OFFICIAL_SOURCE")

    if r.access_model not in ("UNCLEAR",):
        if _evidence_is_missing(r.access_evidence):
            flags.add("NO_OFFICIAL_SOURCE")
            corrections.append("ACCESS_MODEL has a substantive value but ACCESS_EVIDENCE is empty -> flagged NO_OFFICIAL_SOURCE")
        elif not _evidence_is_official(r.access_evidence):
            flags.add("NO_OFFICIAL_SOURCE")

    substantive_api = bool(r.api_types) and r.api_types not in (["UNCLEAR"], ["NONE_FOUND"])
    if substantive_api:
        if _evidence_is_missing(r.api_evidence):
            flags.add("NO_OFFICIAL_SOURCE")
            corrections.append("API_TYPES has a substantive value but API_EVIDENCE is empty -> flagged NO_OFFICIAL_SOURCE")
        elif not _evidence_is_official(r.api_evidence):
            flags.add("NO_OFFICIAL_SOURCE")

    # --- 1b. Evidence claimed OFFICIAL but content was never actually read -
    # (V2 fix for v1_findings.md #1 -- WhatsApp Business MCP page was login-
    # gated; domain looked official but content was unconfirmed.)
    for ev in (r.auth_evidence, r.access_evidence, r.api_evidence, r.mcp_evidence):
        if _evidence_needs_verification_flag(ev):
            flags.add("SOURCE_NOT_VERIFIED")
            corrections.append(
                f"Evidence {ev.urls} is tagged OFFICIAL but verified=False "
                f"(content not directly read) -> flagged SOURCE_NOT_VERIFIED"
            )

    # --- 1c. Conditional/plan-dependent access gate, self-reported ---------
    # (V2 fix for v1_findings.md #2 -- Notion/Salesforce style edition gates
    # that used to live only in ACCESS_NOTES prose.)
    if r.access_conditional_gate:
        flags.add("CONDITIONAL_ACCESS")

    # --- 2. MCP: the hard rule from the spec --------------------------------
    # "Never classify MCP as OFFICIAL unless an official source explicitly
    # supports that conclusion." This is enforced here, not just requested
    # of the researcher: if MCP_STATUS == OFFICIAL without official evidence,
    # the pipeline auto-downgrades it to UNCLEAR and records the correction.
    if r.mcp_status == "OFFICIAL" and not _evidence_is_official(r.mcp_evidence):
        corrections.append(
            f"MCP_STATUS was OFFICIAL without qualifying official evidence "
            f"(evidence={r.mcp_evidence.to_dict()}) -> auto-downgraded to UNCLEAR"
        )
        r.mcp_status = "UNCLEAR"
        flags.add("MCP_UNVERIFIED")
    elif r.mcp_status in ("OFFICIAL", "COMMUNITY") and _evidence_is_missing(r.mcp_evidence):
        flags.add("MCP_UNVERIFIED")
    elif r.mcp_status == "OFFICIAL" and not r.mcp_evidence.verified:
        flags.add("MCP_UNVERIFIED")  # official domain, but content not directly confirmed

    # --- 3. Field-level "unclear" flags -------------------------------------
    if (not r.auth_methods) or r.auth_methods == ["UNCLEAR"]:
        flags.add("AUTH_UNCLEAR")
    if r.access_model == "UNCLEAR":
        flags.add("ACCESS_UNCLEAR")
    if (not r.api_types) or r.api_types == ["UNCLEAR"] or r.api_breadth == "UNCLEAR":
        flags.add("API_UNCLEAR")

    # --- 4. Buildability contradiction checks -------------------------------
    contradiction_reason = None
    if r.buildability == "READY":
        if r.access_model not in SELF_SERVE_ACCESS:
            contradiction_reason = f"BUILDABILITY=READY but ACCESS_MODEL={r.access_model} (not self-serve)"
        elif "UNCLEAR" in r.auth_methods or "NONE_FOUND" in r.auth_methods or not r.auth_methods:
            contradiction_reason = f"BUILDABILITY=READY but AUTH_METHODS={r.auth_methods} is not documented"
        elif r.api_breadth in ("NONE", "UNCLEAR") or (not r.api_types) or r.api_types in (["NONE_FOUND"], ["UNCLEAR"]):
            contradiction_reason = f"BUILDABILITY=READY but API_BREADTH={r.api_breadth} / API_TYPES={r.api_types}"

    elif r.buildability == "GATED":
        if r.access_model not in GATED_ACCESS:
            contradiction_reason = f"BUILDABILITY=GATED but ACCESS_MODEL={r.access_model} is not a gated model"

    elif r.buildability == "BLOCKED":
        if r.api_breadth not in ("NONE", "UNCLEAR") and r.api_types not in (["NONE_FOUND"],):
            # A real API surface was found, so BLOCKED needs a stated non-API reason.
            if not r.main_blocker.strip():
                contradiction_reason = "BUILDABILITY=BLOCKED but an API surface was found and MAIN_BLOCKER is empty"

    if contradiction_reason:
        flags.add("BUILDABILITY_CONTRADICTION")
        corrections.append(
            f"{contradiction_reason} -> BUILDABILITY overridden to NEEDS_REVIEW "
            f"(original agent verdict: {r.buildability})"
        )
        r.main_blocker = (r.main_blocker + " " if r.main_blocker else "") + \
            f"[auto-flag] original verdict was {r.buildability}: {contradiction_reason}"
        r.buildability = "NEEDS_REVIEW"

    # --- 5. Non-standard integration model (V2 fix for v1_findings.md #4) --
    # Heuristic: no auth of any kind AND the only API surface is a local CLI
    # AND access model is a self-serve/free "just install it" case -- this
    # combination usually means "no vendor account to gate at all," which is
    # exactly the Sherlock-shaped edge case the assignment's flag vocabulary
    # didn't originally have a label for. This is a heuristic prompt for a
    # human, not an auto-classification -- it never overrides buildability.
    if (
        r.auth_methods == ["NONE_FOUND"]
        and r.api_types == ["CLI"]
        and r.access_model in ("SELF_SERVE_FREE",)
    ):
        flags.add("NON_STANDARD_INTEGRATION_MODEL")

    r.review_flags = sorted(flags)
    return ValidationResult(flags=sorted(flags), corrections=corrections)
