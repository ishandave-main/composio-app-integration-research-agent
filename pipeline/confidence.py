"""
confidence.py -- Stage: Confidence assessment

The researcher (agent stage) reports a self-assessed CONFIDENCE. This stage
does not trust that number blindly -- it recomputes a FINAL confidence from
the review_flags produced by validate.py, and can only ever hold the
agent's confidence steady or downgrade it, never upgrade it. This mirrors
"preserve uncertainty rather than hiding it": a flag always costs
confidence, it never gets overridden away by a confident-sounding claim.
"""

from __future__ import annotations
from .schema import ResearchRecord

# Flags that cap confidence at MEDIUM even if the agent claimed HIGH.
CAPS_AT_MEDIUM = {
    "NO_OFFICIAL_SOURCE", "MCP_UNVERIFIED", "ACCESS_UNCLEAR",
    "AUTH_UNCLEAR", "API_UNCLEAR",
    "SOURCE_NOT_VERIFIED", "CONDITIONAL_ACCESS", "NON_STANDARD_INTEGRATION_MODEL",
}

# Flags/conditions that force confidence to LOW regardless of agent input.
FORCES_LOW = {"BUILDABILITY_CONTRADICTION", "CONFLICTING_SOURCES"}

_ORDER = {"LOW": 0, "MEDIUM": 1, "HIGH": 2}


def assess_confidence(r: ResearchRecord) -> str:
    flags = set(r.review_flags)
    agent_conf = r.confidence if r.confidence in _ORDER else "LOW"

    final = agent_conf

    if flags & FORCES_LOW:
        final = "LOW"
    else:
        # count how many "uncertainty" flags are present -- 2 or more of
        # these compounding is treated as seriously as a hard contradiction
        soft_flags = flags & CAPS_AT_MEDIUM
        if len(soft_flags) >= 2:
            final = "LOW"
        elif len(soft_flags) == 1 and _ORDER[final] > _ORDER["MEDIUM"]:
            final = "MEDIUM"

    if final == "LOW":
        flags.add("LOW_CONFIDENCE")
        r.review_flags = sorted(flags)

    r.final_confidence = final
    return final
