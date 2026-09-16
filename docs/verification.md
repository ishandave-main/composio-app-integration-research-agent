# Verification

This document describes how the final 100-app dataset was checked against live sources after the pipeline ran, and reports the real, measured results -- not an estimate.

## Why verification exists

The research stage is executed by an LLM agent (me, running inside a Claude session) following a documented procedure (`prompts/research_prompt_v2.md`). Agents make mistakes: they can misread a page, over-trust a third-party claim, or miss a page they didn't think to search for. The rule-based pipeline (`pipeline/validate.py`, `confidence.py`, `review_routing.py`) catches *internally inconsistent* or *unsupported* claims, but it cannot catch a claim that is well-evidenced and still wrong. Only checking against the live source can catch that. This stage exists to measure -- not assume -- how often that happens.

## Sample construction

The sample was built to be representative, not cherry-picked for easy wins:

- **13 apps / 14 field-level checks**, spanning 8 of the 10 categories (Finance and Fintech, Communications and Messaging, Marketing Ads Email and Social, Developer Infra and Data Platforms, Data SEO and Scraping, CRM and Sales, Support and Helpdesk).
- Mixes confidence levels: HIGH (Stripe, GitHub), MEDIUM (Xero, Ramp, Copper, Google Ads), LOW would have been in scope too but the sample leans toward fields the pipeline treated as resolvable, since those are the claims worth stress-testing -- an UNCLEAR call verifying as UNCLEAR is itself a useful check (see Slack, Help Scout, Copper below).
- Mixes MCP statuses: OFFICIAL (Stripe, Xero, Ramp, GitHub, Salesforce, Attio), UNCLEAR (Slack, Help Scout), and a case originally recorded NONE_FOUND that verification overturned (Google Ads).
- Deliberately re-checked two cases carried over from V1's original 5-app deep-dive (Salesforce, and Sherlock's non-standard-integration judgment) to confirm they still hold under a second look.
- Deliberately re-checked the two specific "trust but verify" catches from `docs/v1_findings.md` (Help Scout, and the analogous Slack case in V2) to see if a second pass agrees with the original caution.

Method: for each row, the cited evidence URL (or a new query where the original evidence was search-snippet-only) was independently fetched or searched again, and the agent's recorded field value was compared against what that source actually says. Full detail is in `verification/verification_sample.json`.

## Results

**13 / 14 field-level checks correct = 92.9% measured accuracy** on this sample.

| Result | Count |
|---|---|
| Confirmed correct | 13 |
| Confirmed wrong (corrected) | 1 |

The one error: **Google Ads** was recorded `mcp_status: NONE_FOUND`. Google shipped an official, open-source, read-only Google Ads MCP server on 2026-04-28 (`github.com/googleads/google-ads-mcp`, maintained by the Google Ads API team). The original research pass for this app ran the combined auth/access/API search but skipped the separate MCP-specific search step that the V2 procedure calls for -- a process miss, not a bad judgment call. This has been corrected in `research/v2_raw/google-ads.json` (with a `correction_note` field documenting exactly what changed and why) and the pipeline was re-run on the corrected data before producing the final dataset and case study. This is the only value in the final dataset changed as a direct result of verification.

One additional case is worth calling out even though it's scored "correct": **Slack's MCP status** is recorded `UNCLEAR`, carrying forward a V1-methodology catch (a third-party blog's "official Slack MCP server" claim that api.slack.com didn't confirm at the time). Re-verification found stronger circumstantial evidence this time (the target page now returns 401 rather than 404, meaning it exists but is login-gated, plus a detailed third-party writeup describing a Feb 2026 GA launch with named partners) but still no first-party Slack page confirming it directly. `UNCLEAR` is still the honest answer -- but it's a real example of the pipeline's conservatism producing a probable false negative rather than a false positive. That asymmetry (the system is much more likely to under-claim than to fabricate) is a direct, intended consequence of the "never invent, prefer UNCLEAR" reliability rule, and it shows up empirically here, not just as a design intention.

## V1 vs V2

V1 (5 apps) was not run through a separate formal verification sample -- at that scale, the original research itself was already done at maximum depth (3-4 tool calls per app, most claims independently fetched), and the exercise instead was self-inspection: re-reading the 5 records for problems before scaling up. That produced 4 concrete, documented issues (`docs/v1_findings.md`): evidence-verification conflation, plan-dependent access gating hidden in prose, a vocabulary gap (SOAP), and no flag for non-standard integration models (Sherlock). All four were fixed in the V2 schema and procedure before the 95-app run.

V2 (100 apps, including the 5 V1 apps migrated to the new schema) is where a real measured accuracy number exists for the first time, because V2 deliberately traded per-app research depth for coverage (1-2 targeted searches per app instead of 3-4, with WebFetch reserved for ambiguous cases -- see `prompts/research_prompt_v2.md`'s "scale adjustment" section). That tradeoff is exactly what this verification stage was built to check, and the 92.9% figure is the answer: the shallower per-app research is not error-free, but it is not reckless either, and the pipeline's own confidence/review-routing machinery is doing real work -- 90/100 records were auto-routed to human review, and the review reasons (`SOURCE_NOT_VERIFIED` on 83 records, `MCP_UNVERIFIED` on 47) are a direct, honest reflection of "search-snippet evidence, not independently read" rather than a false signal.

## What this means for the dataset

- Treat every `mcp_status: OFFICIAL` or `access_model` classification with `review_flags` containing `SOURCE_NOT_VERIFIED` as **agent-generated and evidence-backed, but not independently confirmed** -- the flag is doing its job by saying exactly that.
- Treat the 13 checks marked correct here as **human-verified** for those specific apps/fields (not the whole record; only the field checked).
- The one correction (Google Ads MCP) is folded into the final dataset used for the pattern analysis and the case study -- the case study numbers below reflect the corrected data, not the original error.
