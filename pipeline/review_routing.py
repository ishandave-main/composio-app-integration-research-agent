"""
review_routing.py -- Stage: Human-review routing

Pure function of the record after validate.py and confidence.py have run.
Decides NEEDS_HUMAN_REVIEW. Kept separate from validate.py/confidence.py
(rather than folded in) so the routing policy -- which is really a business
decision about acceptable risk, not a fact about the data -- can change
independently and be unit tested on its own.
"""

from __future__ import annotations
from .schema import ResearchRecord

# Any one of these flags, on its own, is enough to route to human review.
HARD_ROUTE_FLAGS = {
    "BUILDABILITY_CONTRADICTION", "CONFLICTING_SOURCES", "MCP_UNVERIFIED",
    "SOURCE_NOT_VERIFIED", "NON_STANDARD_INTEGRATION_MODEL",
}


def route_for_review(r: ResearchRecord) -> bool:
    flags = set(r.review_flags)

    needs_review = (
        r.buildability == "NEEDS_REVIEW"
        or r.final_confidence == "LOW"
        or bool(flags & HARD_ROUTE_FLAGS)
    )

    r.needs_human_review = needs_review
    return needs_review
