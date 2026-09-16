# Submission

## Live Case Study

https://claude.ai/artifact/8nre1AjACkQMC9UNPSkQBV

A locally-runnable copy that requires no server or URL is also included in the repository at `case_study/index.html` (and `site/index.html`, an identical deployable copy) -- open either directly in a browser.

## Source Repository

Not yet pushed to a remote -- this repository exists as a local git repo with full commit history (`git log`). GitHub push requires the submitter's own credentials/authentication, so it was not performed automatically. To publish it:

```bash
cd composio-research-agent
git remote add origin <your-github-repo-url>
git push -u origin master
```

## Deliverables

- AI research agent/workflow (`prompts/research_prompt_v1.md`, `prompts/research_prompt_v2.md`, executed against `research/v1_raw/` and `research/v2_raw/`)
- 100-app structured dataset (`data/output/v2/final_dataset.json` / `.csv`, mirrored at `data/output/final_dataset.json` / `.csv`)
- Evidence-backed integration analysis (every substantive field carries a source URL, source type, and a verified/inferred bit)
- Pattern analysis (`data/output/v2/patterns.json`, mirrored at `data/output/patterns.json`)
- Verification sample (`verification/verification_sample.json`, methodology in `docs/verification.md`)
- Human-in-the-loop design (`pipeline/review_routing.py`, README Section 10)
- Recommendations (case study Section 8: Build Now / Setup Required / Outreach-Gated / Investigate-Needs Review)
- Interactive case-study page (`case_study/index.html`)
- Reproducible deterministic pipeline (`pipeline/`, README Section 11 -- actually rerun as part of preparing this submission, see Reproducibility below)
- Tests (`tests/test_pipeline.py`, 43 tests, actually run -- see Test Results below)

## Key Numbers

All read directly from `data/output/v2/patterns.json` / `final_dataset.json` (the canonical, only research version in this repository):

| Metric | Value |
|---|---|
| Total apps | 100 |
| Categories | 10 (10 apps each) |
| READY | 66 |
| FEASIBLE_WITH_SETUP | 12 |
| GATED | 5 |
| NEEDS_REVIEW | 17 |
| Routed to human review | 90 / 100 (90%) |
| Self-serve access | 79% |
| Official MCP server | 56% |
| Any MCP server (official + community) | 80% |
| OAuth2 supported | 66% |
| Verification: fields checked | 14 |
| Verification: correct | 13 |
| Verification: errors found & corrected | 1 (Google Ads MCP status) |
| Verification: measured sample accuracy | 92.9% |

## Important Caveat

**92.9% is measured accuracy on the 14-field verification sample, not demonstrated accuracy across all 100 apps.** It is a real, honest spot-check signal -- 14 checks against roughly 500 substantive field values in the full dataset -- not a census, and it should not be read or repeated as "the agent is 92.9% accurate." The correct statement, used consistently throughout this repository, is: *92.9% measured accuracy on the verification sample.* See `docs/verification.md` for full sampling methodology and limitations.
