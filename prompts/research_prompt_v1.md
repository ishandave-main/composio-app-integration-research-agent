# Research Agent Prompt -- V1

This is the exact procedure the research stage follows for every app. It is
executed by an LLM agent with live web search/fetch tools (in this build:
Claude running interactively with WebSearch/WebFetch; the same prompt is
designed to be portable to a scripted Claude API call with the server-side
web_search tool -- see README "Extending to a standalone script").

The output of this stage is ONE raw JSON file per app, matching
`pipeline.schema.ResearchRecord`, saved to `research/v1_raw/<app_id>.json`.
This raw file is never treated as final -- it is always run through
`pipeline/validate.py`, `confidence.py`, `review_routing.py` before use.

---

## Inputs

- APP: application name
- CATEGORY: supplied category (do not re-derive)
- WEBSITE_HINT: starting domain/doc URL, if provided

## Procedure

1. **Find official developer documentation.** Search for
   `"<APP> developer documentation"`, `"<APP> API docs"`, `site:<hinted domain>
   developers`. Prefer a docs.*, developer.*, or api.* subdomain of the
   app's own domain, or the app's official GitHub org.

2. **Description.** One sentence, from the product's own marketing/docs
   page, not from search-result snippets alone -- fetch the page.

3. **Authentication.** Read the official auth/API-getting-started docs.
   Classify AUTH_METHODS using the controlled vocabulary (OAUTH2, API_KEY,
   BASIC, TOKEN, OTHER, NONE_FOUND, UNCLEAR). Multiple values allowed
   (e.g. an app can support both OAUTH2 and API_KEY). Record the exact
   doc URL(s) as evidence, and tag each URL's `source_type` as OFFICIAL
   or THIRD_PARTY. NONE_FOUND means you looked and confirmed no auth
   exists to find; UNCLEAR means you could not determine it from
   available sources -- these are not the same thing.

4. **Access model.** Distinguish "an API exists" from "developer access
   is self-serve." Look specifically for: can you sign up and get a key
   immediately (SELF_SERVE_FREE), is there a free trial then paywall
   (SELF_SERVE_TRIAL), is it paid-only from the start (PAID), does it
   require an internal admin/workspace-owner to enable it
   (ADMIN_GATED), does it require a partnership agreement
   (PARTNER_GATED), or does it require contacting sales
   (CONTACT_SALES)? A pricing page or "request access" form is strong
   evidence -- use it.

5. **API surface.** Classify API_TYPES and API_BREADTH from the actual
   API reference (endpoint list, object model), not from marketing
   copy. BROAD = wide surface covering most core objects/actions;
   MODERATE = a real but limited surface; NARROW = one or two
   endpoints/webhooks only; NONE = no programmatic surface found.

6. **MCP status.** Search `"<APP> MCP server"`, `"<APP> Model Context
   Protocol"`, check the app's official docs/GitHub for an MCP
   announcement or reference implementation. OFFICIAL requires the app
   vendor itself (their docs domain or their own GitHub org) to publish
   or endorse it. A third-party or community MCP server (e.g. a
   personal GitHub repo, an unofficial package) is COMMUNITY, never
   OFFICIAL, no matter how polished. If you are not sure who built it,
   it is COMMUNITY or UNCLEAR, never OFFICIAL.

7. **Buildability.** Apply the definitions exactly as specified (READY /
   FEASIBLE_WITH_SETUP / GATED / BLOCKED / NEEDS_REVIEW). State
   MAIN_BLOCKER as a short phrase, not a repeat of the access model
   enum.

8. **Confidence.** HIGH = every substantive field has direct official
   evidence and no ambiguity was encountered. MEDIUM = mostly official
   evidence but at least one field required inference or a secondary
   source. LOW = evidence is thin, conflicting, or largely third-party.
   This is a self-assessment; the pipeline's confidence.py stage will
   independently recompute and may downgrade it -- it can never upgrade
   it, so over-claiming HIGH here buys nothing.

9. **Self-flag known issues.** If you noticed two official sources
   disagree, set review_flags to include CONFLICTING_SOURCES yourself
   rather than silently picking one. The validation stage adds its own
   flags on top of whatever you set; it never removes flags you set.

## Hard rules (do not violate)

- Never invent a URL. If you did not actually open/read a page, do not
  cite it as evidence.
- A homepage or generic marketing page is NOT evidence for a technical
  classification (auth, API, MCP). It may support ACCESS_NOTES context
  at most.
- If you cannot verify something, the value is UNCLEAR -- never guess a
  plausible-sounding answer.
- Tag every evidence URL's source_type honestly. Do not mark a
  third-party blog OFFICIAL because it looks credible.

## Output format

A single JSON object matching this shape (see `pipeline/schema.py` for
the authoritative definition):

```json
{
  "app": "string",
  "category": "string",
  "description": "string",
  "auth_methods": ["OAUTH2"],
  "auth_evidence": {"urls": ["https://..."], "source_type": "OFFICIAL"},
  "access_model": "SELF_SERVE_FREE",
  "access_notes": "string",
  "access_evidence": {"urls": ["https://..."], "source_type": "OFFICIAL"},
  "api_types": ["REST"],
  "api_breadth": "BROAD",
  "api_notes": "string",
  "api_evidence": {"urls": ["https://..."], "source_type": "OFFICIAL"},
  "mcp_status": "NONE_FOUND",
  "mcp_evidence": {"urls": [], "source_type": "NONE"},
  "buildability": "READY",
  "main_blocker": "string or empty",
  "confidence": "HIGH",
  "review_flags": [],
  "sources": ["https://... top sources actually used"],
  "input_website_hint": "string"
}
```
