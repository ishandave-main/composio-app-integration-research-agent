# V1 Findings -- 5-App Test Sample

**Sample:** Stripe (Finance and Fintech), Salesforce (CRM and Sales), Notion
(Productivity and Project Management), Sherlock (Data SEO and Scraping),
WhatsApp Business (Communications and Messaging) -- chosen to span
different categories and, deliberately, different expected outcomes: a
clean READY case, an enterprise CRM with edition nuance, an app with a
plan-dependent access gate, a non-SaaS edge case, and a genuinely
contested access model.

**Result:** 3/5 READY (Stripe, Salesforce, Notion), 2/5 correctly routed to
NEEDS_REVIEW (Sherlock, WhatsApp Business). 0 fabricated URLs. 0 auth
misclassifications found on re-check. 1 MCP claim required a self-flag
(WhatsApp) rather than a clean OFFICIAL. Full outputs: `data/output/v1/`.

## What worked

- **Validation caught what it was designed to catch.** A synthetic
  smoke-test record with `MCP_STATUS=OFFICIAL` and no evidence was
  auto-downgraded to `UNCLEAR` and flagged `MCP_UNVERIFIED` by
  `validate.py` -- confirmed before running on real apps (see repo commit
  history / smoke test in the pipeline build step).
- **Confidence scoring is not just a pass-through.** WhatsApp Business was
  self-rated `MEDIUM` by the research stage, but two review flags
  (`CONFLICTING_SOURCES`, which hard-forces LOW) pulled it down to `LOW`
  automatically, and that's what routed it to human review -- not my
  subjective feel about the app.
- **The Sherlock edge case did not get force-fit into READY/BLOCKED.**
  Sherlock is a local open-source CLI with no vendor, no account, no
  auth -- it doesn't fit the "call a vendor API on a user's behalf" model
  the other 99 apps mostly do. V1 correctly refused to guess and routed it
  to NEEDS_REVIEW with a specific main_blocker explaining *why* it's
  ambiguous, instead of forcing a false-confident BLOCKED or READY.

## Problems found (real, not hypothetical)

### 1. "Official domain" evidence and "verified content" evidence got conflated
For WhatsApp Business's MCP claim, I found `developers.facebook.com/documentation/mcp/whatsapp-business-tools-mcp`
via search -- clearly Meta's own docs domain and URL path -- but the page
itself was login-gated, so I never actually read its content. I tagged
the evidence `source_type: OFFICIAL` (domain-based) and separately
self-flagged `MCP_UNVERIFIED` to compensate, but the schema has no way to
distinguish "I read this official page and it confirms X" from "this URL
is clearly on the vendor's official domain but I could not read what it
says." Those are different evidence strengths and should not both collapse
into `source_type: OFFICIAL`.
**V2 fix:** add a third evidence field, `verified: true/false`
(content actually read vs. URL/domain inferred only), and have
`validate.py` auto-flag any substantive claim rest on `verified: false`
evidence, rather than relying on the researcher to remember to self-flag.

### 2. Plan-dependent / edition-dependent gating lives only in free text
Both Notion (PAT creation disabled by default on Business/Enterprise plans
until an admin enables it) and Salesforce (API access depends on the org's
purchased edition) have a real admin-gate buried inside `ACCESS_NOTES`
prose, while `ACCESS_MODEL` stayed `SELF_SERVE_FREE` and `BUILDABILITY`
stayed `READY`. The rule-based validator only reads structured enum
fields, so this nuance -- which matters a lot for a Product Ops person
deciding what to build first -- currently cannot trigger a flag or a
confidence downgrade on its own.
**V2 fix:** add a structured `access_conditional_gate: true/false` field
the research stage must set explicitly whenever a caveat like this exists,
and have `validate.py` cap confidence at MEDIUM and add a new flag
(`CONDITIONAL_ACCESS`) whenever it's true, instead of trusting prose to
carry the signal.

### 3. Controlled vocabulary gaps forced an imprecise tag, and I initially got it wrong
Salesforce's SOAP/Bulk/Streaming/Metadata/Tooling APIs don't fit
`API_TYPES`'s options (`REST, GRAPHQL, RPC, SDK_ONLY, CLI, OTHER,
NONE_FOUND, UNCLEAR`). My first draft mis-tagged this as `SDK_ONLY`
(wrong -- client libraries are wrappers around REST/SOAP, not a separate
access surface); I caught and corrected it to `REST + OTHER` during
self-review before this even reached you, but `OTHER` is a lossy
catch-all -- a reviewer scanning the final table can't tell if `OTHER`
means SOAP, gRPC, or something else without opening `API_NOTES`.
**V2 fix:** either extend the vocabulary (e.g. add `SOAP` explicitly,
since it's common enough across the 100-app set to be worth a real
label) or require `API_NOTES` to be non-empty whenever `OTHER` is used
(already true here, but not yet enforced by a rule).

### 4. REVIEW_FLAGS has no flag for "this doesn't fit the integration model at all"
Sherlock isn't ambiguous because evidence conflicts or is missing -- it's
ambiguous because the whole "vendor API + auth + access tier" frame the
other fields assume doesn't apply to a local CLI tool with no company
backend. I approximated this with `ACCESS_UNCLEAR`, which is not really
what's going on (access *is* clear: it's "pip install, no gate" -- the
real issue is category fit). Right now this relies entirely on
`BUILDABILITY=NEEDS_REVIEW` plus a clear `MAIN_BLOCKER` sentence to
carry the signal, which works but isn't queryable/countable the way a
proper flag would be.
**V2 fix:** add `NON_STANDARD_INTEGRATION_MODEL` to the flag vocabulary
for the small number of apps (open-source CLIs, tools with no vendor
account concept) where this applies -- I'd guess a handful in the
Data/SEO/Scraping and AI Research categories given what's in the CSV
(Sherlock, Mermaid CLI, possibly others).

## Not a problem, but worth naming for the interview

`OTHER` and `UNCLEAR`/`NONE_FOUND` are easy to confuse in a rushed pass --
`NONE_FOUND` should mean "I positively confirmed there is nothing here"
(Sherlock's auth: I read the README, no auth exists) vs `UNCLEAR` meaning
"I could not determine this." Both appeared correctly used in this
5-app sample, but it's a distinction worth stress-testing again at 100
apps, since it's an easy place for a rushed pass to default to `UNCLEAR`
when `NONE_FOUND` is actually knowable, or vice versa.
