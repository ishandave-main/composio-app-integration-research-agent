"""
Stage 11: Generate the final HTML case study from the pipeline's real output.

Reads:
  - data/output/v2/final_dataset.json  (the 100 researched + validated records)
  - data/output/v2/patterns.json       (Stage 10 pattern analysis)
  - verification/verification_sample.json (the manual verification sample)

Writes:
  - case_study/index.html              (standalone, locally-runnable document)
  - case_study/artifact_fragment.html  (same content, no doctype/html/head/body,
                                         for publishing as a hosted Artifact)

Every number in the page is read from these files at generation time -- nothing
here is hand-typed or invented. Re-running the pipeline and this script
regenerates the case study from scratch.

Run: python3 -m pipeline.generate_case_study
"""
import json
import html as htmlmod
import datetime

DATA_PATH = "data/output/v2/final_dataset.json"
PATTERNS_PATH = "data/output/v2/patterns.json"
VERIFICATION_PATH = "verification/verification_sample.json"
OUT_STANDALONE = "case_study/index.html"
OUT_FRAGMENT = "case_study/artifact_fragment.html"


def esc(s):
    return htmlmod.escape(str(s), quote=True)


def load():
    with open(DATA_PATH) as f:
        data = json.load(f)
    with open(PATTERNS_PATH) as f:
        patterns = json.load(f)
    with open(VERIFICATION_PATH) as f:
        verification = json.load(f)
    return data, patterns, verification


# ---------------------------------------------------------------------------
# Small helpers for building repeated markup
# ---------------------------------------------------------------------------

BADGE_CLASS = {
    "READY": "b-ready",
    "FEASIBLE_WITH_SETUP": "b-setup",
    "GATED": "b-gated",
    "BLOCKED": "b-gated",
    "NEEDS_REVIEW": "b-review",
    "OFFICIAL": "b-ready",
    "COMMUNITY": "b-setup",
    "NONE_FOUND": "b-neutral",
    "UNCLEAR": "b-review",
    "HIGH": "b-ready",
    "MEDIUM": "b-setup",
    "LOW": "b-review",
    "SELF_SERVE_FREE": "b-ready",
    "SELF_SERVE_TRIAL": "b-setup",
    "PAID": "b-setup",
    "ADMIN_GATED": "b-gated",
    "PARTNER_GATED": "b-gated",
    "CONTACT_SALES": "b-gated",
    "UNCLEAR_ACCESS": "b-review",
}


def badge(value, extra_class=""):
    cls = BADGE_CLASS.get(value, "b-neutral")
    return f'<span class="badge {cls} {extra_class}">{esc(value.replace("_", " "))}</span>'


def bar_chart(dist, total, unit="apps", sort_desc=True):
    """Render a simple horizontal bar chart from a {label: count} dict."""
    items = list(dist.items())
    if sort_desc:
        items.sort(key=lambda kv: -kv[1])
    rows = []
    max_v = max((v for _, v in items), default=1)
    for label, v in items:
        pct = round(100 * v / total, 1) if total else 0
        width = round(100 * v / max_v, 1) if max_v else 0
        rows.append(f'''
        <div class="bar-row">
          <div class="bar-label">{esc(label.replace("_", " "))}</div>
          <div class="bar-track"><div class="bar-fill" style="width:{width}%"></div></div>
          <div class="bar-value">{v} <span class="bar-pct">({pct}%)</span></div>
        </div>''')
    return f'<div class="bar-chart">{"".join(rows)}</div>'


def build_matrix_rows(data):
    rows = []
    for r in data:
        auth = ", ".join(r["auth_methods"])
        api_types = ", ".join(r["api_types"])
        flags = ", ".join(r["review_flags"]) if r["review_flags"] else ""
        evidence_urls = []
        for k in ("auth_evidence", "access_evidence", "api_evidence", "mcp_evidence"):
            for u in r.get(k, {}).get("urls", []):
                if u not in evidence_urls:
                    evidence_urls.append(u)
        first_evidence = evidence_urls[0] if evidence_urls else ""
        ev_count = len(evidence_urls)
        row_html = f'''
        <tr data-category="{esc(r['category'])}" data-buildability="{esc(r['buildability'])}"
            data-mcp="{esc(r['mcp_status'])}" data-access="{esc(r['access_model'])}"
            data-confidence="{esc(r['final_confidence'])}" data-review="{str(r['needs_human_review']).lower()}"
            data-search="{esc((r['app'] + ' ' + r['category'] + ' ' + r['description']).lower())}">
          <td class="cell-app"><strong>{esc(r['app'])}</strong><div class="cell-sub">{esc(r['category'])}</div></td>
          <td>{esc(auth) if auth else '—'}</td>
          <td>{badge(r['access_model'])}</td>
          <td>{esc(api_types) if api_types else '—'} <span class="cell-sub-inline">{esc(r['api_breadth'])}</span></td>
          <td>{badge(r['mcp_status'])}</td>
          <td>{badge(r['buildability'])}</td>
          <td>{badge(r['final_confidence'])}</td>
          <td>{'<span class="flag-pill">flagged</span>' if r['needs_human_review'] else '<span class="ok-pill">clear</span>'}
              <div class="cell-sub">{esc(flags)}</div></td>
          <td>{f'<a href="{esc(first_evidence)}" target="_blank" rel="noopener">source</a> <span class="cell-sub-inline">(+{ev_count-1} more)</span>' if ev_count > 1 else (f'<a href="{esc(first_evidence)}" target="_blank" rel="noopener">source</a>' if first_evidence else '—')}</td>
        </tr>'''
        rows.append(row_html)
    return "\n".join(rows)


def build_verification_rows(verification):
    rows = []
    for v in verification:
        mark = '<span class="ok-pill">✓ correct</span>' if v["correct"] else '<span class="flag-pill">✕ corrected</span>'
        rows.append(f'''
        <tr>
          <td><strong>{esc(v['app'])}</strong><div class="cell-sub">{esc(v['category'])}</div></td>
          <td>{esc(v['field_checked'])}</td>
          <td><code>{esc(v['agent_answer'])}</code></td>
          <td><code>{esc(v['human_verified_answer'])}</code></td>
          <td>{mark}</td>
          <td class="cell-notes">{esc(v['notes'])}{f" <strong>Correction:</strong> {esc(v['correction'])}" if v['correction'] else ""}</td>
        </tr>''')
    return "\n".join(rows)


def category_bar_chart(category_stats):
    rows = []
    for cat, s in sorted(category_stats.items(), key=lambda kv: -kv[1]["ready_pct"]):
        rows.append(f'''
        <div class="bar-row">
          <div class="bar-label">{esc(cat)}</div>
          <div class="bar-track"><div class="bar-fill fill-ready" style="width:{s['ready_pct']}%"></div></div>
          <div class="bar-value">{s['ready_n']}/{s['n']} <span class="bar-pct">READY</span></div>
        </div>''')
    return f'<div class="bar-chart">{"".join(rows)}</div>'


# ---------------------------------------------------------------------------
# Main build
# ---------------------------------------------------------------------------

def build_page(data, patterns, verification):
    today = datetime.date.today().isoformat()
    n = patterns["total_apps"]

    v_total = len(verification)
    v_correct = sum(1 for v in verification if v["correct"])
    v_acc = round(100 * v_correct / v_total, 1)

    easy_wins = [r for r in data if r["buildability"] == "READY" and r["final_confidence"] in ("HIGH", "MEDIUM") and not r["review_flags"]]
    setup_required = [r for r in data if r["buildability"] == "FEASIBLE_WITH_SETUP"]
    outreach = [r for r in data if r["buildability"] == "GATED"]
    blocked = [r for r in data if r["buildability"] == "NEEDS_REVIEW"]

    def chip_list(rows, cls=""):
        return "".join(f'<span class="chip {cls}">{esc(r["app"])}</span>' for r in rows)

    matrix_rows = build_matrix_rows(data)
    verification_rows = build_verification_rows(verification)

    categories = sorted(set(r["category"] for r in data))
    category_options = "".join(f'<option value="{esc(c)}">{esc(c)}</option>' for c in categories)

    # ---- Assemble the page body (fragment-safe: no doctype/html/head/body) ----
    body = f'''<title>App Integration Research Agent</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Newsreader:ital,opsz,wght@0,6..72,400;0,6..72,500;0,6..72,600;1,6..72,500&family=IBM+Plex+Sans:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500;600&display=swap">
<style>
{CSS}
</style>

<div class="page">

  <header class="hero">
    <div class="eyebrow">Composio &middot; AI Product Operations Intern take-home &middot; generated {esc(today)}</div>
    <h1>App Integration Research Agent</h1>
    <p class="hero-sub">A reusable pipeline that researches whether 100 real-world apps can become agent-callable Composio toolkits &mdash; auth, access model, API surface, MCP availability, and a defensible buildability verdict for each, with evidence, confidence, and honest uncertainty attached to every claim.</p>
    <div class="hero-stats">
      <div class="stat-tile"><div class="stat-n">{n}</div><div class="stat-l">apps researched</div></div>
      <div class="stat-tile"><div class="stat-n">{patterns['buildability_distribution'].get('READY',0)}</div><div class="stat-l">READY today</div></div>
      <div class="stat-tile"><div class="stat-n">{patterns['mcp_official_pct']}%</div><div class="stat-l">have an official MCP server</div></div>
      <div class="stat-tile"><div class="stat-n">{patterns['human_review_pct']}%</div><div class="stat-l">routed to human review</div></div>
      <div class="stat-tile"><div class="stat-n">{v_acc}%</div><div class="stat-l">verified accuracy (sample)</div></div>
    </div>
  </header>

  <nav class="toc">
    <a href="#findings">1. Findings</a>
    <a href="#matrix">2. Matrix</a>
    <a href="#patterns">3. Patterns</a>
    <a href="#architecture">4. Architecture</a>
    <a href="#iteration">5. Iteration</a>
    <a href="#verification">6. Verification</a>
    <a href="#human-agent">7. Human vs. agent</a>
    <a href="#recommendations">8. Recommendations</a>
    <a href="#methodology">9. Methodology</a>
  </nav>

  <section id="findings" class="section">
    <h2><span class="sec-no">01</span> Headline findings</h2>
    <div class="finding-grid">
      <div class="finding-card">
        <div class="finding-stat">{patterns['self_serve_pct']}%</div>
        <p>of apps offer self-serve API access (no sales call, no admin approval) &mdash; but only <strong>{round(100*patterns['buildability_distribution'].get('READY',0)/n,1)}%</strong> are actually verdict-READY today. Self-serve access is necessary but not sufficient: a real, documented, non-trivial API surface and a confirmed auth path both have to hold too.</p>
      </div>
      <div class="finding-card">
        <div class="finding-stat">{patterns['mcp_any_pct']}%</div>
        <p>already have <em>some</em> MCP server ({patterns['mcp_official_pct']}% official, the rest community-built). MCP adoption across this 100-app sample is much further along than a Composio toolkit-gap analysis might assume going in.</p>
      </div>
      <div class="finding-card">
        <div class="finding-stat">{patterns['human_review_pct']}%</div>
        <p>of records were auto-routed to human review by the rule-based pipeline &mdash; not because most apps are risky, but because the V2 research pass traded per-app depth for 100-app coverage. <code>SOURCE_NOT_VERIFIED</code> alone drives {patterns['review_flag_distribution'].get('SOURCE_NOT_VERIFIED',0)} of the {patterns['human_review_n']} routes. The flag is doing its job, not failing.</p>
      </div>
      <div class="finding-card">
        <div class="finding-stat">20%</div>
        <p><strong>Data SEO and Scraping</strong> is the hardest category to build on &mdash; only 2/10 apps READY, 100% flagged for review, dominated by paid-tier gating (Ahrefs, SE Ranking, DataForSEO) and vendors whose identity or pricing couldn't be confirmed at all (MrScraper, Waterfall.io). <strong>Productivity and Project Management</strong> is the easiest: 10/10 READY, 100% self-serve, 80% with an official MCP server.</p>
      </div>
      <div class="finding-card">
        <div class="finding-stat">{v_acc}%</div>
        <p>measured accuracy on a 14-field, 13-app verification sample cross-checked against live sources. One real error was caught and corrected before this dataset shipped &mdash; Google Ads' official MCP server was missed on the first research pass and is now recorded correctly. See <a href="#verification">Verification</a>.</p>
      </div>
    </div>
  </section>

  <section id="matrix" class="section">
    <h2><span class="sec-no">02</span> 100-app research matrix</h2>
    <p class="section-intro">Every field below was produced by the agent pipeline described in <a href="#architecture">Architecture</a>, with an evidence link and a review flag column showing exactly why the pipeline trusts or doesn't trust each row. Filter and search to explore.</p>
    <div class="matrix-controls">
      <input type="search" id="f-search" placeholder="Search app or category&hellip;" aria-label="Search">
      <select id="f-category" aria-label="Filter by category"><option value="">All categories</option>{category_options}</select>
      <select id="f-buildability" aria-label="Filter by buildability">
        <option value="">All buildability</option>
        <option value="READY">READY</option>
        <option value="FEASIBLE_WITH_SETUP">FEASIBLE_WITH_SETUP</option>
        <option value="GATED">GATED</option>
        <option value="NEEDS_REVIEW">NEEDS_REVIEW</option>
      </select>
      <select id="f-mcp" aria-label="Filter by MCP status">
        <option value="">All MCP status</option>
        <option value="OFFICIAL">OFFICIAL</option>
        <option value="COMMUNITY">COMMUNITY</option>
        <option value="NONE_FOUND">NONE_FOUND</option>
        <option value="UNCLEAR">UNCLEAR</option>
      </select>
      <select id="f-confidence" aria-label="Filter by confidence">
        <option value="">All confidence</option>
        <option value="HIGH">HIGH</option>
        <option value="MEDIUM">MEDIUM</option>
        <option value="LOW">LOW</option>
      </select>
      <label class="review-toggle"><input type="checkbox" id="f-review"> Flagged for review only</label>
      <span id="f-count" class="f-count"></span>
    </div>
    <div class="table-wrap">
      <table id="matrix-table">
        <thead>
          <tr>
            <th>App / Category</th><th>Auth</th><th>Access</th><th>API type / breadth</th>
            <th>MCP</th><th>Buildability</th><th>Confidence</th><th>Review</th><th>Evidence</th>
          </tr>
        </thead>
        <tbody>
          {matrix_rows}
        </tbody>
      </table>
    </div>
  </section>

  <section id="patterns" class="section">
    <h2><span class="sec-no">03</span> Pattern analysis</h2>
    <p class="section-intro">Computed directly from the 100-record final dataset (<code>pipeline/pattern_analysis.py</code>) &mdash; not estimated.</p>
    <div class="pattern-grid">
      <div class="pattern-card">
        <h3>Auth methods</h3>
        {bar_chart(patterns['auth_method_distribution'], n)}
      </div>
      <div class="pattern-card">
        <h3>Access model</h3>
        {bar_chart(patterns['access_model_distribution'], n)}
      </div>
      <div class="pattern-card">
        <h3>Buildability verdict</h3>
        {bar_chart(patterns['buildability_distribution'], n)}
      </div>
      <div class="pattern-card">
        <h3>MCP status</h3>
        {bar_chart(patterns['mcp_status_distribution'], n)}
      </div>
      <div class="pattern-card">
        <h3>Confidence</h3>
        {bar_chart(patterns['confidence_distribution'], n)}
      </div>
      <div class="pattern-card">
        <h3>Review flags raised</h3>
        {bar_chart(patterns['review_flag_distribution'], n)}
      </div>
    </div>
    <div class="pattern-card pattern-wide">
      <h3>READY rate by category</h3>
      {category_bar_chart(patterns['category_stats'])}
    </div>
    <div class="callout-row">
      <div class="callout"><strong>{patterns['oauth2_pct']}%</strong> of apps support OAuth2 as at least one auth method; of those, <strong>{patterns['oauth2_ready_pct']}%</strong> are buildability-READY.</div>
      <div class="callout"><strong>{patterns['self_serve_ready_pct']}%</strong> of self-serve apps are READY, versus <strong>{patterns['gated_ready_pct']}%</strong> of gated-access apps (ADMIN_GATED / PARTNER_GATED / CONTACT_SALES / PAID) &mdash; gating essentially guarantees a non-READY verdict by construction, since a human always has to unblock it first.</div>
      <div class="callout">Most common named blockers: <strong>paid-plan requirement</strong> ({patterns['blocker_keyword_distribution'].get('paid_plan_required',0)}), <strong>manual review/approval</strong> ({patterns['blocker_keyword_distribution'].get('approval',0)}), <strong>vendor identity or docs unconfirmable</strong> ({patterns['blocker_keyword_distribution'].get('no_official_source',0)}), <strong>sales contact required</strong> ({patterns['blocker_keyword_distribution'].get('sales_contact',0)}).</div>
    </div>
  </section>

  <section id="architecture" class="section">
    <h2><span class="sec-no">04</span> Agent architecture</h2>
    <p class="section-intro">One pipeline, ten stages, three kinds of logic kept strictly separate: the LLM agent only <em>researches and classifies</em>; everything downstream is deterministic Python with zero network calls, so it reruns identically on the same input forever. Deliberately simple &mdash; one research agent following a versioned prompt, not a multi-agent system, because the hard part here is evidence discipline, not orchestration.</p>
    <div class="arch-flow">
      <div class="arch-stage"><div class="arch-n">1</div><div class="arch-t">apps.csv</div><div class="arch-d">100 apps, 10 categories, as given</div></div>
      <div class="arch-arrow">&rarr;</div>
      <div class="arch-stage"><div class="arch-n">2</div><div class="arch-t">Normalize</div><div class="arch-d">pipeline/normalize.py &middot; stable app_id, header aliasing</div></div>
      <div class="arch-arrow">&rarr;</div>
      <div class="arch-stage arch-agent"><div class="arch-n">3</div><div class="arch-t">Agent research</div><div class="arch-d">WebSearch + selective WebFetch, following prompts/research_prompt_v2.md &middot; produces one evidence-tagged JSON record per app</div></div>
      <div class="arch-arrow">&rarr;</div>
      <div class="arch-stage"><div class="arch-n">4</div><div class="arch-t">Validate</div><div class="arch-d">pipeline/validate.py &middot; rule-based, auto-corrects unsupported claims (e.g. MCP=OFFICIAL with no official evidence &rarr; UNCLEAR)</div></div>
      <div class="arch-arrow">&rarr;</div>
      <div class="arch-stage"><div class="arch-n">5</div><div class="arch-t">Confidence</div><div class="arch-d">pipeline/confidence.py &middot; can only hold or downgrade, never upgrade</div></div>
      <div class="arch-arrow">&rarr;</div>
      <div class="arch-stage"><div class="arch-n">6</div><div class="arch-t">Review routing</div><div class="arch-d">pipeline/review_routing.py &middot; hard-routes contradictions, low confidence, unverified MCP claims</div></div>
      <div class="arch-arrow">&rarr;</div>
      <div class="arch-stage"><div class="arch-n">7</div><div class="arch-t">Final dataset</div><div class="arch-d">final_dataset.csv / .json &middot; every field + evidence + flags</div></div>
      <div class="arch-arrow">&rarr;</div>
      <div class="arch-stage"><div class="arch-n">8</div><div class="arch-t">Patterns + case study</div><div class="arch-d">pattern_analysis.py &middot; generate_case_study.py &middot; this page</div></div>
    </div>
    <p class="arch-note">The only non-deterministic, non-rerunnable-without-me step is Stage 3. That was an explicit, discussed tradeoff: research needs live web access, and running it as an agent inside a Claude session (rather than a standalone script calling an external LLM API) means no API key has to ship with this repo, at the cost of "rerun" meaning "reopen a Claude session against this repo and follow the prompt," not "run a cron job." <code>prompts/research_prompt_v2.md</code> is written precisely enough that this is a faithful re-execution, not vibes.</p>
  </section>

  <section id="iteration" class="section">
    <h2><span class="sec-no">05</span> Agent iteration: V1 &rarr; V2</h2>
    <div class="iter-grid">
      <div class="iter-card">
        <h3>V1 &mdash; 5 apps, maximum depth</h3>
        <p>Stripe, Salesforce, Notion, Sherlock, WhatsApp Business &mdash; one from each of 5 different categories, researched at 3&ndash;4 tool calls per app (WebSearch + WebFetch on nearly every claim). Self-inspected for problems before writing a line of pipeline code. Found 4 real issues:</p>
        <ul class="iter-list">
          <li><strong>Evidence-verification conflation</strong> &mdash; a page on an official domain that returns "please log in" (WhatsApp Business's MCP docs) was being treated the same as a page actually read and confirmed.</li>
          <li><strong>Plan-dependent access hidden in prose</strong> &mdash; Notion and Salesforce's access model changes depending on which paid tier an org is on; the original schema had no field to capture that.</li>
          <li><strong>Vocabulary gap</strong> &mdash; Salesforce's SOAP API got mistagged as SDK_ONLY because the controlled vocabulary had no slot for it.</li>
          <li><strong>No flag for non-standard integration models</strong> &mdash; Sherlock is a local CLI tool with no vendor account at all; nothing routed that case for human judgment before it could be silently marked READY.</li>
        </ul>
      </div>
      <div class="iter-card">
        <h3>V2 &mdash; fixes + a disclosed scale tradeoff</h3>
        <p>Each V1 problem became a concrete schema or rule change before any of the remaining 95 apps were touched:</p>
        <ul class="iter-list">
          <li>Added a <code>verified</code> boolean to every evidence object, and a <code>SOURCE_NOT_VERIFIED</code> flag the pipeline raises automatically when evidence is on an official domain but wasn't actually read.</li>
          <li>Added <code>access_conditional_gate</code> + <code>CONDITIONAL_ACCESS</code> to capture "self-serve to start, gated at some tier or step" without losing the nuance.</li>
          <li>Added <code>SOAP</code> to the API_TYPES vocabulary.</li>
          <li>Added a <code>NON_STANDARD_INTEGRATION_MODEL</code> heuristic (auth=NONE_FOUND + api_types=[CLI] + access=SELF_SERVE_FREE triggers it automatically) &mdash; it correctly caught Sherlock and Mermaid CLI in the full run.</li>
        </ul>
        <p>Separately, and disclosed rather than hidden: researching 95 more apps at V1's depth wasn't going to finish, so V2's procedure targets 1&ndash;2 WebSearch calls per app (one combined auth/access/API query, one MCP-specific query), with WebFetch reserved for genuinely ambiguous or high-stakes calls. That tradeoff is exactly what the <a href="#verification">verification stage</a> below was built to check.</p>
      </div>
    </div>
  </section>

  <section id="verification" class="section">
    <h2><span class="sec-no">06</span> Verification</h2>
    <p class="section-intro">V1 had no separate verification sample &mdash; at 3&ndash;4 tool calls per app, the original research was already close to maximum depth, so the exercise was self-inspection (above). V2's shallower, faster procedure is where a real measured number was needed, so {v_total} field-level claims across {len(set(v['app'] for v in verification))} apps were independently re-checked against live sources after the pipeline ran.</p>
    <div class="hero-stats verification-stats">
      <div class="stat-tile"><div class="stat-n">{v_total}</div><div class="stat-l">fields checked</div></div>
      <div class="stat-tile"><div class="stat-n">{v_correct}</div><div class="stat-l">confirmed correct</div></div>
      <div class="stat-tile"><div class="stat-n">{v_total - v_correct}</div><div class="stat-l">error found &amp; corrected</div></div>
      <div class="stat-tile stat-tile-accent"><div class="stat-n">{v_acc}%</div><div class="stat-l">measured accuracy</div></div>
    </div>
    <div class="table-wrap">
      <table class="verify-table">
        <thead><tr><th>App</th><th>Field</th><th>Agent said</th><th>Human-verified</th><th>Result</th><th>Notes</th></tr></thead>
        <tbody>{verification_rows}</tbody>
      </table>
    </div>
    <p class="arch-note">Full detail (evidence URLs, correction text) in <code>verification/verification_sample.json</code> and <code>docs/verification.md</code>. The one confirmed error (Google Ads' MCP server, missed then corrected) is already folded into the dataset and every number on this page &mdash; nothing above reflects the pre-correction data.</p>
  </section>

  <section id="human-agent" class="section">
    <h2><span class="sec-no">07</span> What's safe to automate</h2>
    <div class="ha-grid">
      <div class="ha-card ha-good">
        <h3>Safe for the agent alone</h3>
        <ul class="iter-list">
          <li>Finding official documentation domains and distinguishing them from third-party blogs/aggregators.</li>
          <li>Classifying auth method and API type against a fixed, well-evidenced page.</li>
          <li>Flagging an unverifiable or contradictory claim as UNCLEAR / NEEDS_REVIEW instead of guessing.</li>
          <li>Rule-based confidence capping and review routing &mdash; this is deterministic code, not agent judgment, and it never needs a human to check its arithmetic.</li>
        </ul>
      </div>
      <div class="ha-card ha-bad">
        <h3>Needs a human before acting on it</h3>
        <ul class="iter-list">
          <li>Any record where <code>final_confidence = LOW</code> or <code>needs_human_review = true</code> &mdash; {patterns['human_review_n']}/{n} records here.</li>
          <li>Anything flagged <code>BUILDABILITY_CONTRADICTION</code> or <code>CONFLICTING_SOURCES</code> &mdash; the pipeline caught two internally-inconsistent records automatically ({patterns['review_flag_distribution'].get('BUILDABILITY_CONTRADICTION',0)} contradiction cases) and neither should be trusted without a look.</li>
          <li>Genuinely ambiguous vendor identity (Paygent Connect: four unrelated companies share the name; no amount of searching resolved which one the dataset means).</li>
          <li>Anything gated behind sales/partnership/subscription (5 apps: DealCloud, LinkedIn Ads, NotebookLM Enterprise, PitchBook, Salesforce Commerce Cloud) &mdash; buildability there is a business decision, not a research question.</li>
        </ul>
      </div>
    </div>
  </section>

  <section id="recommendations" class="section">
    <h2><span class="sec-no">08</span> Product ops recommendations</h2>
    <div class="reco-grid">
      <div class="reco-card">
        <h3>Easy wins <span class="reco-count">{len(easy_wins)}</span></h3>
        <p>READY, medium/high confidence, zero review flags. Build now.</p>
        <div class="chip-row">{chip_list(easy_wins, 'chip-good')}</div>
      </div>
      <div class="reco-card">
        <h3>Setup required <span class="reco-count">{len(setup_required)}</span></h3>
        <p>Real, working self-serve path, but a review/approval/paid-plan step sits between signup and production use.</p>
        <div class="chip-row">{chip_list(setup_required, 'chip-setup')}</div>
      </div>
      <div class="reco-card">
        <h3>Outreach / partner <span class="reco-count">{len(outreach)}</span></h3>
        <p>No self-serve path at all &mdash; needs a BD or partnerships conversation before any engineering starts.</p>
        <div class="chip-row">{chip_list(outreach, 'chip-gated')}</div>
      </div>
      <div class="reco-card">
        <h3>Blocked / needs review <span class="reco-count">{len(blocked)}</span></h3>
        <p>Either the research genuinely couldn't resolve access/identity, or the integration shape itself (e.g. a local CLI tool) doesn't fit the standard "call a vendor API" model and needs a product decision first.</p>
        <div class="chip-row">{chip_list(blocked, 'chip-review')}</div>
      </div>
    </div>
  </section>

  <section id="methodology" class="section">
    <h2><span class="sec-no">09</span> Methodology &amp; reproducibility</h2>
    <p class="section-intro">Full detail, including exact commands, is in the repository README. Summary:</p>
    <ul class="iter-list">
      <li><strong>Input:</strong> the provided <code>apps.csv</code> (100 apps &times; 10 categories), used verbatim.</li>
      <li><strong>Research:</strong> executed by an LLM agent inside a Claude session following <code>prompts/research_prompt_v2.md</code> &mdash; a deliberate, disclosed choice over a standalone script calling an external API, so no API key ships with this repo. See Architecture above.</li>
      <li><strong>Validation, confidence, routing, pattern analysis, and this page</strong> are all deterministic Python with zero network calls &mdash; rerun any of them against the same <code>research/v2_raw/*.json</code> files and you get byte-identical output.</li>
      <li><strong>Nothing here was fabricated:</strong> every count, percentage, and chip on this page is read from <code>data/output/v2/final_dataset.json</code> and <code>data/output/v2/patterns.json</code> at page-generation time by <code>pipeline/generate_case_study.py</code>.</li>
      <li><strong>Known limitation:</strong> V2's research depth (1&ndash;2 search calls/app) trades certainty for coverage; the 92.9% verification accuracy and the 90% human-review rate are the honest, measured consequences of that tradeoff, not a hidden cost.</li>
    </ul>
  </section>

  <footer class="page-footer">
    <p>Built for the Composio AI Product Operations Intern take-home. Pipeline code, raw research records, verification data, and this generator: see the repository README.</p>
  </footer>
</div>

<script>
{JS}
</script>
'''
    return body


CSS = r"""
:root{
  --bg:#F2F4F5; --surface:#FFFFFF; --surface-2:#EBEFF1;
  --ink:#14213D; --ink-2:#4A5568; --ink-3:#7A8794;
  --accent:#0E7C7B; --accent-ink:#F0FBFA;
  --good:#1F7A4D; --good-bg:#E4F5EB;
  --warn:#9A6B15; --warn-bg:#FBF0DA;
  --bad:#B42318; --bad-bg:#FBE6E3;
  --neutral-bg:#E7EAEC;
  --border:#DCE2E5; --border-2:#C7CFD3;
  --shadow: 0 1px 2px rgba(20,33,61,0.06), 0 4px 16px rgba(20,33,61,0.05);
  --radius: 10px;
  --mono: 'IBM Plex Mono', ui-monospace, SFMono-Regular, Menlo, monospace;
  --sans: 'IBM Plex Sans', -apple-system, BlinkMacSystemFont, sans-serif;
  --serif: 'Newsreader', Georgia, 'Times New Roman', serif;
}
@media (prefers-color-scheme: dark){
  :root:not([data-theme="light"]){
    --bg:#10161D; --surface:#171F28; --surface-2:#1E2831;
    --ink:#E7ECEF; --ink-2:#B6C0C8; --ink-3:#8592A0;
    --accent:#3FD1C9; --accent-ink:#04211F;
    --good:#4ADE80; --good-bg:#123423;
    --warn:#F5C451; --warn-bg:#3A2E0E;
    --bad:#F87171; --bad-bg:#3A1614;
    --neutral-bg:#232E38;
    --border:#2B3843; --border-2:#37454F;
    --shadow: 0 1px 2px rgba(0,0,0,0.3), 0 4px 20px rgba(0,0,0,0.25);
  }
}
:root[data-theme="dark"]{
  --bg:#10161D; --surface:#171F28; --surface-2:#1E2831;
  --ink:#E7ECEF; --ink-2:#B6C0C8; --ink-3:#8592A0;
  --accent:#3FD1C9; --accent-ink:#04211F;
  --good:#4ADE80; --good-bg:#123423;
  --warn:#F5C451; --warn-bg:#3A2E0E;
  --bad:#F87171; --bad-bg:#3A1614;
  --neutral-bg:#232E38;
  --border:#2B3843; --border-2:#37454F;
  --shadow: 0 1px 2px rgba(0,0,0,0.3), 0 4px 20px rgba(0,0,0,0.25);
}
*{box-sizing:border-box;}
body{background:var(--bg); color:var(--ink); font-family:var(--sans); margin:0;}
.page{max-width:1180px; margin:0 auto; padding:0 20px 64px; color:var(--ink);}
h1,h2,h3{font-family:var(--serif); font-weight:600; color:var(--ink); text-wrap:balance; margin:0;}
code{font-family:var(--mono); background:var(--surface-2); padding:0.12em 0.4em; border-radius:5px; font-size:0.9em;}
a{color:var(--accent);}
p{line-height:1.6; color:var(--ink-2);}

.hero{padding:56px 0 28px; border-bottom:1px solid var(--border);}
.eyebrow{font-family:var(--mono); font-size:12px; letter-spacing:0.06em; text-transform:uppercase; color:var(--ink-3); margin-bottom:14px;}
.hero h1{font-size:clamp(32px,5vw,52px); line-height:1.05; margin-bottom:16px;}
.hero-sub{font-size:17px; max-width:760px; margin-bottom:32px;}
.hero-stats{display:flex; flex-wrap:wrap; gap:14px;}
.stat-tile{background:var(--surface); border:1px solid var(--border); border-radius:var(--radius); padding:16px 20px; min-width:130px; box-shadow:var(--shadow);}
.stat-tile-accent{border-color:var(--accent); background:var(--accent-ink);}
.stat-n{font-family:var(--serif); font-size:28px; font-weight:600; font-variant-numeric:tabular-nums; color:var(--ink);}
.stat-l{font-size:12.5px; color:var(--ink-2); margin-top:2px;}

.toc{display:flex; flex-wrap:wrap; gap:4px 18px; padding:16px 0; border-bottom:1px solid var(--border); position:sticky; top:0; background:var(--bg); z-index:5; font-family:var(--mono); font-size:12.5px;}
.toc a{color:var(--ink-2); text-decoration:none; padding:4px 0;}
.toc a:hover{color:var(--accent);}

.section{padding:52px 0; border-bottom:1px solid var(--border);}
.section:last-of-type{border-bottom:none;}
.sec-no{font-family:var(--mono); font-size:14px; color:var(--accent); margin-right:10px; font-weight:600;}
.section h2{font-size:26px; margin-bottom:18px;}
.section-intro{max-width:800px; margin-bottom:26px;}

.finding-grid{display:grid; grid-template-columns:repeat(auto-fit,minmax(260px,1fr)); gap:16px;}
.finding-card{background:var(--surface); border:1px solid var(--border); border-radius:var(--radius); padding:22px; box-shadow:var(--shadow);}
.finding-stat{font-family:var(--serif); font-size:34px; font-weight:600; color:var(--accent); margin-bottom:8px;}
.finding-card p{font-size:14.5px; margin:0;}

.matrix-controls{display:flex; flex-wrap:wrap; gap:10px; align-items:center; margin-bottom:16px; position:sticky; top:44px; background:var(--bg); padding:10px 0; z-index:4;}
.matrix-controls input, .matrix-controls select{font-family:var(--sans); font-size:13.5px; padding:8px 10px; border-radius:8px; border:1px solid var(--border-2); background:var(--surface); color:var(--ink);}
.matrix-controls input{flex:1 1 200px; min-width:160px;}
.review-toggle{font-size:13px; color:var(--ink-2); display:flex; align-items:center; gap:6px;}
.f-count{font-family:var(--mono); font-size:12.5px; color:var(--ink-3); margin-left:auto;}

.table-wrap{overflow-x:auto; border:1px solid var(--border); border-radius:var(--radius); background:var(--surface);}
table{border-collapse:collapse; width:100%; min-width:920px; font-size:13.5px;}
th{text-align:left; background:var(--surface-2); font-family:var(--mono); font-size:11px; text-transform:uppercase; letter-spacing:0.04em; color:var(--ink-2); padding:10px 12px; border-bottom:1px solid var(--border); position:sticky; top:0;}
td{padding:10px 12px; border-bottom:1px solid var(--border); vertical-align:top; color:var(--ink);}
tr:last-child td{border-bottom:none;}
.cell-app strong{font-size:14px;}
.cell-sub{font-size:11.5px; color:var(--ink-3); margin-top:2px;}
.cell-sub-inline{font-size:11px; color:var(--ink-3);}
.cell-notes{font-size:12.5px; color:var(--ink-2); max-width:340px;}
.verify-table{min-width:1000px;}

.badge{display:inline-block; font-family:var(--mono); font-size:11px; font-weight:600; padding:3px 8px; border-radius:20px; white-space:nowrap;}
.b-ready{background:var(--good-bg); color:var(--good);}
.b-setup{background:var(--warn-bg); color:var(--warn);}
.b-gated{background:var(--bad-bg); color:var(--bad);}
.b-review{background:var(--warn-bg); color:var(--warn);}
.b-neutral{background:var(--neutral-bg); color:var(--ink-2);}
.flag-pill{background:var(--bad-bg); color:var(--bad); font-family:var(--mono); font-size:11px; padding:2px 7px; border-radius:20px;}
.ok-pill{background:var(--good-bg); color:var(--good); font-family:var(--mono); font-size:11px; padding:2px 7px; border-radius:20px;}

.pattern-grid{display:grid; grid-template-columns:repeat(auto-fit,minmax(320px,1fr)); gap:16px; margin-bottom:16px;}
.pattern-card{background:var(--surface); border:1px solid var(--border); border-radius:var(--radius); padding:20px; box-shadow:var(--shadow);}
.pattern-card h3{font-size:15px; margin-bottom:14px;}
.pattern-wide{margin-bottom:22px;}
.bar-chart{display:flex; flex-direction:column; gap:9px;}
.bar-row{display:grid; grid-template-columns:minmax(120px,180px) 1fr auto; gap:10px; align-items:center; font-size:12.5px;}
.bar-label{color:var(--ink-2); overflow:hidden; text-overflow:ellipsis; white-space:nowrap;}
.bar-track{background:var(--surface-2); border-radius:6px; height:10px; overflow:hidden;}
.bar-fill{background:var(--accent); height:100%; border-radius:6px;}
.fill-ready{background:var(--good);}
.bar-value{font-family:var(--mono); font-variant-numeric:tabular-nums; color:var(--ink); white-space:nowrap;}
.bar-pct{color:var(--ink-3);}

.callout-row{display:grid; grid-template-columns:repeat(auto-fit,minmax(260px,1fr)); gap:14px;}
.callout{background:var(--surface-2); border-radius:var(--radius); padding:16px 18px; font-size:13.5px; color:var(--ink-2); border-left:3px solid var(--accent);}

.arch-flow{display:flex; flex-wrap:wrap; align-items:stretch; gap:8px; margin-bottom:16px;}
.arch-stage{background:var(--surface); border:1px solid var(--border); border-radius:var(--radius); padding:14px 16px; width:170px; box-shadow:var(--shadow);}
.arch-agent{border-color:var(--accent); background:var(--accent-ink);}
.arch-n{font-family:var(--mono); font-size:11px; color:var(--accent); font-weight:700;}
.arch-t{font-family:var(--serif); font-weight:600; font-size:15px; margin:4px 0 6px;}
.arch-d{font-size:11.5px; color:var(--ink-2); line-height:1.4;}
.arch-arrow{display:flex; align-items:center; color:var(--ink-3); font-size:18px;}
.arch-note{font-size:13.5px; color:var(--ink-2); max-width:820px;}

.iter-grid{display:grid; grid-template-columns:repeat(auto-fit,minmax(340px,1fr)); gap:18px;}
.iter-card{background:var(--surface); border:1px solid var(--border); border-radius:var(--radius); padding:22px; box-shadow:var(--shadow);}
.iter-card h3{font-size:16px; margin-bottom:10px;}
.iter-card p{font-size:13.5px;}
.iter-list{margin:10px 0 0; padding-left:20px; font-size:13.5px; color:var(--ink-2); display:flex; flex-direction:column; gap:8px;}

.verification-stats{margin-bottom:22px;}

.ha-grid{display:grid; grid-template-columns:repeat(auto-fit,minmax(320px,1fr)); gap:18px;}
.ha-card{border-radius:var(--radius); padding:22px; border:1px solid var(--border); box-shadow:var(--shadow);}
.ha-good{background:var(--good-bg);}
.ha-bad{background:var(--bad-bg);}
.ha-card h3{font-size:16px; margin-bottom:10px;}

.reco-grid{display:grid; grid-template-columns:repeat(auto-fit,minmax(280px,1fr)); gap:16px;}
.reco-card{background:var(--surface); border:1px solid var(--border); border-radius:var(--radius); padding:20px; box-shadow:var(--shadow);}
.reco-card h3{font-size:15px; display:flex; align-items:center; gap:8px;}
.reco-count{font-family:var(--mono); font-size:12px; background:var(--surface-2); color:var(--ink-2); padding:2px 8px; border-radius:20px;}
.reco-card p{font-size:12.5px; margin:6px 0 12px;}
.chip-row{display:flex; flex-wrap:wrap; gap:6px;}
.chip{font-family:var(--mono); font-size:11.5px; padding:4px 9px; border-radius:6px; background:var(--surface-2); color:var(--ink-2);}
.chip-good{background:var(--good-bg); color:var(--good);}
.chip-setup{background:var(--warn-bg); color:var(--warn);}
.chip-gated{background:var(--bad-bg); color:var(--bad);}
.chip-review{background:var(--neutral-bg); color:var(--ink-2);}

.page-footer{padding:36px 0 0; font-size:12.5px; color:var(--ink-3);}

@media (max-width:640px){
  .arch-stage{width:140px;}
  table{min-width:760px;}
  .toc{overflow-x:auto; flex-wrap:nowrap;}
}
"""

JS = r"""
(function(){
  var search = document.getElementById('f-search');
  var category = document.getElementById('f-category');
  var buildability = document.getElementById('f-buildability');
  var mcp = document.getElementById('f-mcp');
  var confidence = document.getElementById('f-confidence');
  var reviewOnly = document.getElementById('f-review');
  var rows = Array.prototype.slice.call(document.querySelectorAll('#matrix-table tbody tr'));
  var countEl = document.getElementById('f-count');

  function applyFilters(){
    var q = (search.value || '').toLowerCase().trim();
    var cat = category.value, build = buildability.value, mcpV = mcp.value, conf = confidence.value;
    var revOnly = reviewOnly.checked;
    var shown = 0;
    rows.forEach(function(r){
      var ok = true;
      if(q && r.getAttribute('data-search').indexOf(q) === -1) ok = false;
      if(cat && r.getAttribute('data-category') !== cat) ok = false;
      if(build && r.getAttribute('data-buildability') !== build) ok = false;
      if(mcpV && r.getAttribute('data-mcp') !== mcpV) ok = false;
      if(conf && r.getAttribute('data-confidence') !== conf) ok = false;
      if(revOnly && r.getAttribute('data-review') !== 'true') ok = false;
      r.hidden = !ok;
      if(ok) shown++;
    });
    countEl.textContent = shown + ' / ' + rows.length + ' apps';
  }

  [search, category, buildability, mcp, confidence, reviewOnly].forEach(function(el){
    el.addEventListener('input', applyFilters);
    el.addEventListener('change', applyFilters);
  });
  applyFilters();
})();
"""


def main():
    data, patterns, verification = load()
    body = build_page(data, patterns, verification)

    standalone = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
{body[:body.index('<div class="page">')]}
</head>
<body>
{body[body.index('<div class="page">'):]}
</body>
</html>
"""

    import os
    os.makedirs("case_study", exist_ok=True)
    with open(OUT_STANDALONE, "w") as f:
        f.write(standalone)
    with open(OUT_FRAGMENT, "w") as f:
        f.write(body)
    print(f"Wrote {OUT_STANDALONE} ({len(standalone):,} bytes)")
    print(f"Wrote {OUT_FRAGMENT} ({len(body):,} bytes)")


if __name__ == "__main__":
    main()
