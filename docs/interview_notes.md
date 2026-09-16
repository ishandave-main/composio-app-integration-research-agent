---
description: Concise Q&A prep for defending this submission in an interview
---

# Interview Notes

## 1. What did you build?

A reusable pipeline that researches whether 100 real-world apps can become agent-callable Composio toolkits, and produces a structured, evidence-backed answer for each -- auth method, access model, API surface, MCP status, a buildability verdict, confidence, and a machine-readable list of exactly why the pipeline does or doesn't trust each record. Not a one-off spreadsheet: rerun the deterministic half against a different app list and it produces the same kind of output.

## 2. Why did you use an agent?

Because the research task itself -- finding the real developer docs, distinguishing an official source from a third-party blog's claim, reading past marketing copy to actual auth mechanics -- needs judgment and live web access, and that's exactly what an LLM agent with search/fetch tools is good at. Everything that *doesn't* need judgment (validating internal consistency, scoring confidence, routing for review, computing statistics) is deliberately plain deterministic Python instead, precisely so it's cheap, auditable, and reruns identically forever. The agent is scoped to the one stage that actually needs it.

## 3. How does the workflow work?

`apps.csv` → normalize → agent research (writes one evidence-tagged JSON record per app) → rule-based validation (auto-corrects unsupported claims, e.g. downgrades an unevidenced `MCP=OFFICIAL` to `UNCLEAR`) → confidence scoring (can only hold or downgrade what the agent claimed) → human-review routing → final dataset → pattern analysis → verification sample → HTML case study. See the architecture diagram in `README.md` Section 4.

## 4. Why V1 → V2?

The assignment explicitly required proving the pipeline on a small sample before scaling. V1 researched 5 apps at near-exhaustive depth and was self-inspected for problems before any pipeline code was scaled up -- found 4 real issues (evidence-verification conflation, plan-dependent access hidden in prose, a SOAP vocabulary gap, no flag for non-standard integration models like a local CLI tool). Each became a concrete schema or rule change before the remaining 95 apps were touched. Doing this in the wrong order -- building the schema first, researching second -- would have meant discovering the same 4 problems 100 times instead of once.

## 5. What went wrong?

Two honest things, not hidden:

1. **A real research error, caught by verification.** Google Ads' official MCP server was missed on the first research pass -- the combined auth/access/API search ran, but the separate MCP-specific search step (part of the documented V2 procedure) was skipped for that one app. Verification caught it, and it was corrected in the source record and the pipeline re-run before this dataset was finalized.
2. **A schema/taxonomy bug caught by the test suite while preparing this submission.** Google Ads' API type was recorded as `GRPC`, but the controlled vocabulary only defines `RPC` -- a naming inconsistency, not a factual error (gRPC is a form of RPC). `tests/test_pipeline.py` asserts every shipped field uses the controlled vocabulary, caught this, and it was fixed and the pipeline re-run. This is exactly why that test exists.

## 6. How did you measure accuracy?

Built a 14-field verification sample across 13 apps, spanning 8 of the 10 categories and a mix of confidence levels and MCP statuses, then independently re-checked each claim against a live source (re-fetched or re-searched separately from the evidence that produced the original claim, wherever possible). 13/14 correct = 92.9%. This is **sample accuracy**, not a population-wide guarantee -- 14 checks against roughly 500 substantive field values in the full dataset is a real, meaningful spot-check, not a census. Full methodology in `docs/verification.md`.

## 7. Why are so many records human-reviewed?

90/100 records are routed for review, and it's a direct, disclosed consequence of one decision: V2 targets 1-2 search calls per app (to make 100 apps tractable) instead of V1's 3-4 per app, so most evidence is inferred from an official domain or a search snippet rather than independently read. The pipeline flags that honestly (`SOURCE_NOT_VERIFIED`, 83 of the 90 routes) instead of hiding the uncertainty behind a confident-looking record. A 90% review rate at this research depth is the system doing its job -- the alternative would be to silently present shallow research as if it were deep research, which is exactly what the assignment's reliability rules prohibit.

## 8. What would you improve with another week?

In priority order: (1) burn down the `SOURCE_NOT_VERIFIED` backlog specifically, since it's the single largest driver of the review rate -- targeted re-fetches on just those ~83 records would likely convert a meaningful fraction to auto-approved; (2) grow the verification sample from 14 to ~40-50 fields for a tighter confidence interval; (3) add source-freshness tracking so a stale record (e.g. an MCP-status claim from months ago) gets automatically re-flagged; (4) cross-reference against Composio's actual existing toolkit catalog so "buildable" becomes "not yet built."

## 9. What did the agent do better than a human?

Consistency and coverage: the same controlled vocabulary, the same "never claim OFFICIAL without official evidence" discipline, applied identically across 100 apps in one sitting, with every claim traceable to a URL. A human researcher doing this manually would almost certainly be faster on any single app but less consistent across 100 -- fatigue, drift in what counts as "good enough" evidence, and inconsistent note-taking are real risks a rule-based pipeline downstream of the agent doesn't have.

## 10. Where is human judgment still essential?

Anywhere the question stops being "what does the evidence say" and becomes "what should we do about it": genuinely ambiguous vendor identity (e.g. "Paygent Connect," which matches four unrelated real companies and no amount of searching resolved which one), conflicting official-looking sources, anything gated behind a sales or partnership conversation (that's a BD decision, not a research question), and non-standard integration shapes like a local CLI tool with no vendor account at all, where the right move is a product decision about whether a CLI-wrapper toolkit is even in scope -- not something the pipeline should decide on its own.
