"""
Stage 10: Pattern analysis over the final dataset.

Reads data/output/v2/final_dataset.json (the pipeline's output) and computes
real, measured distributions and cross-tabs -- nothing here is invented or
estimated. Writes data/output/v2/patterns.json for the case study to consume.

Run: python3 -m pipeline.pattern_analysis
"""
import json
import os
from collections import Counter, defaultdict

IN_PATH = "data/output/v2/final_dataset.json"
OUT_PATH = "data/output/v2/patterns.json"


def pct(n, d):
    return round(100 * n / d, 1) if d else 0.0


def main():
    with open(IN_PATH) as f:
        data = json.load(f)
    n = len(data)

    # --- Basic distributions ---
    auth_counter = Counter()
    for r in data:
        for a in r["auth_methods"]:
            auth_counter[a] += 1

    access_counter = Counter(r["access_model"] for r in data)
    buildability_counter = Counter(r["buildability"] for r in data)
    mcp_counter = Counter(r["mcp_status"] for r in data)
    confidence_counter = Counter(r["final_confidence"] for r in data)
    api_type_counter = Counter()
    for r in data:
        for t in r["api_types"]:
            api_type_counter[t] += 1
    api_breadth_counter = Counter(r["api_breadth"] for r in data)

    flag_counter = Counter()
    for r in data:
        for fl in r["review_flags"]:
            flag_counter[fl] += 1

    human_review_n = sum(1 for r in data if r["needs_human_review"])

    # --- Self-serve vs gated ---
    self_serve_models = {"SELF_SERVE_FREE", "SELF_SERVE_TRIAL"}
    gated_models = {"ADMIN_GATED", "PARTNER_GATED", "CONTACT_SALES", "PAID"}
    self_serve_n = sum(1 for r in data if r["access_model"] in self_serve_models)
    gated_n = sum(1 for r in data if r["access_model"] in gated_models)
    unclear_access_n = sum(1 for r in data if r["access_model"] == "UNCLEAR")

    # --- OAuth2 / API key prevalence ---
    oauth2_n = sum(1 for r in data if "OAUTH2" in r["auth_methods"])
    api_key_n = sum(1 for r in data if "API_KEY" in r["auth_methods"] or "TOKEN" in r["auth_methods"])

    # --- MCP availability ---
    mcp_official_n = mcp_counter.get("OFFICIAL", 0)
    mcp_any_n = mcp_official_n + mcp_counter.get("COMMUNITY", 0)

    # --- Buildability / access by category ---
    by_category = defaultdict(list)
    for r in data:
        by_category[r["category"]].append(r)

    category_stats = {}
    for cat, rows in by_category.items():
        c_n = len(rows)
        ready_n = sum(1 for r in rows if r["buildability"] == "READY")
        gated_or_blocked = sum(1 for r in rows if r["buildability"] in ("GATED", "BLOCKED"))
        needs_review_n = sum(1 for r in rows if r["buildability"] == "NEEDS_REVIEW")
        self_serve_cat_n = sum(1 for r in rows if r["access_model"] in self_serve_models)
        mcp_official_cat_n = sum(1 for r in rows if r["mcp_status"] == "OFFICIAL")
        human_review_cat_n = sum(1 for r in rows if r["needs_human_review"])
        category_stats[cat] = {
            "n": c_n,
            "ready_pct": pct(ready_n, c_n),
            "ready_n": ready_n,
            "gated_or_blocked_n": gated_or_blocked,
            "gated_or_blocked_pct": pct(gated_or_blocked, c_n),
            "needs_review_n": needs_review_n,
            "self_serve_pct": pct(self_serve_cat_n, c_n),
            "mcp_official_pct": pct(mcp_official_cat_n, c_n),
            "human_review_pct": pct(human_review_cat_n, c_n),
        }

    easiest = sorted(category_stats.items(), key=lambda kv: -kv[1]["ready_pct"])
    hardest = sorted(category_stats.items(), key=lambda kv: kv[1]["ready_pct"])

    # --- Common blockers (non-empty main_blocker text, categorized by keyword) ---
    blocker_texts = [r["main_blocker"] for r in data if r.get("main_blocker")]
    blocker_keywords = Counter()
    keyword_map = {
        "approval": ["review", "approval", "approve"],
        "admin_required": ["admin"],
        "sales_contact": ["sales", "subscription", "data license", "contact"],
        "paid_plan_required": ["paid", "enterprise", "plan"],
        "no_official_source": ["could not", "no official", "unconfirmed", "not confirmed"],
        "non_standard_model": ["cli", "local", "not a company-backed"],
    }
    for text in blocker_texts:
        t_low = text.lower()
        matched = False
        for label, kws in keyword_map.items():
            if any(kw in t_low for kw in kws):
                blocker_keywords[label] += 1
                matched = True
        if not matched:
            blocker_keywords["other"] += 1

    # --- Auth x Access x Buildability relationship ---
    oauth2_ready_n = sum(
        1 for r in data if "OAUTH2" in r["auth_methods"] and r["buildability"] == "READY"
    )
    self_serve_ready_n = sum(
        1
        for r in data
        if r["access_model"] in self_serve_models and r["buildability"] == "READY"
    )
    gated_ready_n = sum(
        1 for r in data if r["access_model"] in gated_models and r["buildability"] == "READY"
    )

    patterns = {
        "total_apps": n,
        "auth_method_distribution": dict(auth_counter),
        "access_model_distribution": dict(access_counter),
        "buildability_distribution": dict(buildability_counter),
        "mcp_status_distribution": dict(mcp_counter),
        "confidence_distribution": dict(confidence_counter),
        "api_type_distribution": dict(api_type_counter),
        "api_breadth_distribution": dict(api_breadth_counter),
        "review_flag_distribution": dict(flag_counter),
        "human_review_n": human_review_n,
        "human_review_pct": pct(human_review_n, n),
        "self_serve_n": self_serve_n,
        "self_serve_pct": pct(self_serve_n, n),
        "gated_n": gated_n,
        "gated_pct": pct(gated_n, n),
        "unclear_access_n": unclear_access_n,
        "unclear_access_pct": pct(unclear_access_n, n),
        "oauth2_n": oauth2_n,
        "oauth2_pct": pct(oauth2_n, n),
        "api_key_or_token_n": api_key_n,
        "api_key_or_token_pct": pct(api_key_n, n),
        "mcp_official_n": mcp_official_n,
        "mcp_official_pct": pct(mcp_official_n, n),
        "mcp_any_n": mcp_any_n,
        "mcp_any_pct": pct(mcp_any_n, n),
        "category_stats": category_stats,
        "easiest_categories": [c for c, _ in easiest[:3]],
        "hardest_categories": [c for c, _ in hardest[:3]],
        "blocker_keyword_distribution": dict(blocker_keywords),
        "oauth2_ready_n": oauth2_ready_n,
        "oauth2_ready_pct": pct(oauth2_ready_n, oauth2_n),
        "self_serve_ready_n": self_serve_ready_n,
        "self_serve_ready_pct": pct(self_serve_ready_n, self_serve_n),
        "gated_ready_n": gated_ready_n,
        "gated_ready_pct": pct(gated_ready_n, gated_n),
    }

    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w") as f:
        json.dump(patterns, f, indent=2)
    print(f"Wrote {OUT_PATH}")
    print(json.dumps(patterns, indent=2))


if __name__ == "__main__":
    main()
