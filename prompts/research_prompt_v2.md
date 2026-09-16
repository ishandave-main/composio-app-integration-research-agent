# Research Agent Prompt -- V2

V2 = V1's procedure (`research_prompt_v1.md`) plus the fixes from
`docs/v1_findings.md`, plus an explicit **scale adjustment** for running
across 100 apps in one pass instead of 5.

## What changed from V1

1. **Evidence now carries a `verified` bit.** `verified: true` means the
   researcher actually opened and read the cited page. `verified: false`
   means the URL is confidently on the vendor's own official domain (by
   path/naming convention or strong corroboration) but the content itself
   could not be fetched (login wall, JS-only page, blocked). `OFFICIAL +
   verified:false` still counts as `source_type: OFFICIAL` for the
   NO_OFFICIAL_SOURCE check, but `validate.py` now auto-flags it
   `SOURCE_NOT_VERIFIED` and caps confidence at MEDIUM -- no more relying
   on the researcher to remember to self-flag it (V1 problem #1).

2. **`access_conditional_gate: true/false` is now mandatory.** Set `true`
   whenever access is not uniform across all customers -- e.g. a feature
   gated behind a specific plan tier, an admin has to flip a setting, or
   an edition/SKU determines whether the API is available at all. This
   used to live only in prose (V1 problem #2); now it drives an automatic
   `CONDITIONAL_ACCESS` flag and confidence cap.

3. **`API_TYPES` gained `SOAP`** as an explicit value instead of forcing
   SOAP-based APIs into the `OTHER` catch-all (V1 problem #3).

4. **New flag `NON_STANDARD_INTEGRATION_MODEL`.** For apps with no
   vendor/account concept at all (local CLI tools, single-purpose open
   source utilities) -- `validate.py` now auto-detects the common shape of
   this (NONE_FOUND auth + CLI-only + free install) and flags it, on top
   of whatever the researcher's own `main_blocker` explains (V1 problem #4).

## Scale adjustment for the 100-app pass

The V1 procedure fetched 2-4 full pages per app (auth docs, access/pricing
docs, API reference, MCP search) -- appropriate for a 5-app spot check, not
practical at 100 apps in one sitting without an unreasonable number of
fetches. For the full run:

- **One targeted WebSearch per app** covering docs/auth/access/API in a
  single query is the default (e.g. `"<App> API documentation
  authentication developer access"`). Search result snippets from a
  docs.*/developer.*/api.* subdomain are treated as sufficient
  `verified: true` evidence *only when the snippet itself states the
  fact* (e.g. the snippet text says "use API keys to authenticate") --
  otherwise the page is fetched.
- **One targeted WebSearch per app for MCP** (`"<App> MCP server
  official"` / `"<App> Model Context Protocol"`).
- **WebFetch is used, not skipped,** whenever: the app is in a
  higher-stakes category for buildability calls (Finance/Fintech,
  anything gated), the search snippets disagree with each other, or the
  MCP question can't be resolved from search alone (does the vendor
  themselves host it, or is every result a third-party wrapper?).
- This is a real, disclosed depth tradeoff -- not hidden. It's also why
  the verification stage (manually re-checking a sample against live
  docs) exists: it measures whether the lighter-touch pass holds up, and
  the number is reported honestly either way.

Everything else (controlled vocabularies, hard rules on invented URLs,
NONE_FOUND vs UNCLEAR discipline, self-flagging CONFLICTING_SOURCES) is
unchanged from V1.
