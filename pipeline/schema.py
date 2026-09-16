"""
schema.py

Canonical definition of the research record produced by the App Integration
Research Agent, plus the enums/allowed-value sets used everywhere else in
the pipeline (validation, confidence scoring, analysis).

This is the single source of truth for field names and allowed values.
Every other stage imports from here instead of hardcoding strings, so a
change to the taxonomy only has to happen once.
"""

from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import List, Optional
import json

# ---------------------------------------------------------------------------
# Allowed value sets (controlled vocabularies)
# ---------------------------------------------------------------------------

AUTH_METHODS = {"OAUTH2", "API_KEY", "BASIC", "TOKEN", "OTHER", "NONE_FOUND", "UNCLEAR"}

ACCESS_MODEL = {
    "SELF_SERVE_FREE", "SELF_SERVE_TRIAL", "PAID", "ADMIN_GATED",
    "PARTNER_GATED", "CONTACT_SALES", "UNCLEAR",
}

API_TYPES = {"REST", "GRAPHQL", "RPC", "SOAP", "SDK_ONLY", "CLI", "OTHER", "NONE_FOUND", "UNCLEAR"}

API_BREADTH = {"BROAD", "MODERATE", "NARROW", "NONE", "UNCLEAR"}

MCP_STATUS = {"OFFICIAL", "COMMUNITY", "NONE_FOUND", "UNCLEAR"}

BUILDABILITY = {"READY", "FEASIBLE_WITH_SETUP", "GATED", "BLOCKED", "NEEDS_REVIEW"}

CONFIDENCE = {"HIGH", "MEDIUM", "LOW"}

REVIEW_FLAGS = {
    "NO_OFFICIAL_SOURCE", "CONFLICTING_SOURCES", "LOW_CONFIDENCE",
    "MCP_UNVERIFIED", "ACCESS_UNCLEAR", "AUTH_UNCLEAR", "API_UNCLEAR",
    "BUILDABILITY_CONTRADICTION",
    # V2 additions (pipeline extensions beyond the assignment's suggested list,
    # added in response to concrete V1 5-app-test findings -- see docs/v1_findings.md)
    "SOURCE_NOT_VERIFIED",          # evidence URL is on an official domain but content was not directly read (e.g. login wall)
    "CONDITIONAL_ACCESS",           # access model depends on plan/edition/admin setting, not uniform for all customers
    "NON_STANDARD_INTEGRATION_MODEL",  # app has no vendor/account concept the ACCESS_MODEL taxonomy assumes (e.g. local OSS CLI)
}

SOURCE_TYPES = {"OFFICIAL", "THIRD_PARTY"}


# ---------------------------------------------------------------------------
# Evidence: every technical claim is backed by one or more tagged URLs.
# Tagging OFFICIAL vs THIRD_PARTY at extraction time (not inferred later by
# regex-guessing a domain) is what lets validation catch NO_OFFICIAL_SOURCE
# reliably.
# ---------------------------------------------------------------------------

@dataclass
class Evidence:
    urls: List[str] = field(default_factory=list)
    source_type: str = "OFFICIAL"  # OFFICIAL | THIRD_PARTY | MIXED (derived) | NONE (derived)
    # V2 addition: True only if the researcher actually opened and read the page
    # content. False means the URL is inferred to be official by domain/path
    # (or by third-party corroboration) but the content itself could not be
    # fetched (e.g. a login wall) -- see docs/v1_findings.md problem #1.
    verified: bool = True

    def to_dict(self):
        return {"urls": self.urls, "source_type": self.source_type, "verified": self.verified}

    @staticmethod
    def from_dict(d: dict) -> "Evidence":
        if d is None:
            return Evidence(urls=[], source_type="NONE", verified=False)
        return Evidence(
            urls=d.get("urls", []),
            source_type=d.get("source_type", "NONE"),
            verified=d.get("verified", True),
        )

    @property
    def is_empty(self) -> bool:
        return len(self.urls) == 0


@dataclass
class ResearchRecord:
    app: str
    category: str
    description: str

    auth_methods: List[str] = field(default_factory=list)
    auth_evidence: Evidence = field(default_factory=Evidence)

    access_model: str = "UNCLEAR"
    access_notes: str = ""
    access_evidence: Evidence = field(default_factory=Evidence)

    api_types: List[str] = field(default_factory=list)
    api_breadth: str = "UNCLEAR"
    api_notes: str = ""
    api_evidence: Evidence = field(default_factory=Evidence)

    mcp_status: str = "UNCLEAR"
    mcp_evidence: Evidence = field(default_factory=Evidence)

    buildability: str = "NEEDS_REVIEW"
    main_blocker: str = ""
    # V2 addition: set True when access depends on plan/edition/admin-enablement
    # rather than being uniform for every customer (see v1_findings.md problem #2)
    access_conditional_gate: bool = False

    confidence: str = "LOW"                # agent's self-reported confidence, BEFORE rule overrides
    final_confidence: str = ""             # set by pipeline (confidence.py); may downgrade the above
    needs_human_review: bool = True         # set by pipeline (review_routing.py), not the agent
    review_flags: List[str] = field(default_factory=list)  # set by pipeline, agent may seed some

    sources: List[str] = field(default_factory=list)

    # provenance / pipeline bookkeeping (not researched, filled by the pipeline)
    pipeline_version: str = "v1"
    research_date: str = ""
    input_website_hint: str = ""

    def to_dict(self) -> dict:
        d = asdict(self)
        d["auth_evidence"] = self.auth_evidence.to_dict()
        d["access_evidence"] = self.access_evidence.to_dict()
        d["api_evidence"] = self.api_evidence.to_dict()
        d["mcp_evidence"] = self.mcp_evidence.to_dict()
        return d

    @staticmethod
    def from_dict(d: dict) -> "ResearchRecord":
        d = dict(d)  # shallow copy
        d["auth_evidence"] = Evidence.from_dict(d.get("auth_evidence"))
        d["access_evidence"] = Evidence.from_dict(d.get("access_evidence"))
        d["api_evidence"] = Evidence.from_dict(d.get("api_evidence"))
        d["mcp_evidence"] = Evidence.from_dict(d.get("mcp_evidence"))
        known = set(ResearchRecord.__dataclass_fields__.keys())
        filtered = {k: v for k, v in d.items() if k in known}
        return ResearchRecord(**filtered)

    def to_json(self, indent=2) -> str:
        return json.dumps(self.to_dict(), indent=indent)


# Flat column order for the final CSV export (matches the assignment's field list)
CSV_COLUMNS = [
    "APP", "CATEGORY", "DESCRIPTION",
    "AUTH_METHODS", "AUTH_EVIDENCE",
    "ACCESS_MODEL", "ACCESS_NOTES", "ACCESS_EVIDENCE",
    "API_TYPES", "API_BREADTH", "API_NOTES", "API_EVIDENCE",
    "MCP_STATUS", "MCP_EVIDENCE",
    "BUILDABILITY", "MAIN_BLOCKER",
    "CONFIDENCE", "NEEDS_HUMAN_REVIEW", "REVIEW_FLAGS",
    "SOURCES", "PIPELINE_VERSION", "RESEARCH_DATE",
]


def record_to_csv_row(r: ResearchRecord) -> dict:
    def join(x):
        return "; ".join(x) if isinstance(x, list) else (x or "")

    return {
        "APP": r.app,
        "CATEGORY": r.category,
        "DESCRIPTION": r.description,
        "AUTH_METHODS": join(r.auth_methods),
        "AUTH_EVIDENCE": join(r.auth_evidence.urls),
        "ACCESS_MODEL": r.access_model,
        "ACCESS_NOTES": r.access_notes,
        "ACCESS_EVIDENCE": join(r.access_evidence.urls),
        "API_TYPES": join(r.api_types),
        "API_BREADTH": r.api_breadth,
        "API_NOTES": r.api_notes,
        "API_EVIDENCE": join(r.api_evidence.urls),
        "MCP_STATUS": r.mcp_status,
        "MCP_EVIDENCE": join(r.mcp_evidence.urls),
        "BUILDABILITY": r.buildability,
        "MAIN_BLOCKER": r.main_blocker,
        "CONFIDENCE": r.final_confidence or r.confidence,
        "NEEDS_HUMAN_REVIEW": "TRUE" if r.needs_human_review else "FALSE",
        "REVIEW_FLAGS": join(r.review_flags),
        "SOURCES": join(r.sources),
        "PIPELINE_VERSION": r.pipeline_version,
        "RESEARCH_DATE": r.research_date,
    }
