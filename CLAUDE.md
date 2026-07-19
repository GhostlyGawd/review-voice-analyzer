# CLAUDE.md — Review Voice Analyzer

## What this project is

An automated review-mining pipeline that turns raw customer feedback (GitHub
issues, G2/Capterra reviews, Reddit threads, Discord archives) into a ranked,
counted taxonomy of pain points, wishes, likes, and use cases.

It replicates a methodology the repo owner ran professionally for a
multi-million-dollar Amazon business: **process every review available, break
each one into pieces, categorize each piece, and track mention counts.**
Counts drive everything downstream — the most-mentioned themes become
product priorities and above-the-fold marketing positioning; less-mentioned
themes rank further down, like a hierarchy of needs.

## Why it exists

The owner is validating product opportunities in AI dev tooling. The project
came out of a brainstorming funnel — categories, drilled into subcategories,
product ideas per subcategory — that kept hitting the same wall: every idea
already had competition. The unblock was reframing that wall. Operating
premise: **existing competition is validated demand, not a stop sign.**

The conventional next step after that reframe is customer interviews. This
methodology replaces them: the owner ran it for a multi-million-dollar Amazon
business that was wildly successful and never interviewed a single customer —
exhaustive competitor review analysis stood in for interviews and drove both
product development and marketing positioning (see docs/methodology.md).

The mining output answers the questions that actually matter:

1. Do people pay for the incumbents and still complain?
2. What is the ranked, counted list of what they complain about?
3. What do they wish existed? (This is a ranked list of ventures.)

## Current mining target

**Agent observability & debugging.** Output feeds the PRD for an **agent
trace debugger** — step-through debugging and time-travel replay for AI agent
traces (debugging, not dashboards — that's the wedge vs. observability
platforms).

Competitor field: LangSmith, Langfuse, Braintrust, Arize Phoenix, Opik,
Helicone, AgentOps, Laminar, Maxim, W&B Weave, Galileo, Latitude.

Public issue trackers, with total issue counts validated 2026-07-19:

| Repo | ~Issues |
|---|---|
| Arize-ai/phoenix | 5,948 |
| langfuse/langfuse | 2,738 |
| comet-ml/opik | 697 |
| langchain-ai/langsmith-sdk | 607 |
| AgentOps-AI/agentops | 444 |
| Helicone/helicone | 280 |
| lmnr-ai/lmnr | 133 |

Known competitive flags for the PRD: Maxim ships deterministic replay
(fixed-seed rerun); LangSmith ships an AI debugging assistant ("Polly") that
attacks "why did it fail" from the AI-explains-it angle. Neither invalidates
the idea; positioning must answer both.

## Methodology rules — do not dilute these

1. **Exhaustive beats sampled.** The counts are the signal; partial sampling
   guts them. Process everything available for a source before moving on.
2. **Every piece gets exactly one type:** `pain_point` | `wished_existed` |
   `liked` | `use_case`. Bug reports and complaints are pain_point. Feature
   requests are wished_existed.
3. **Reuse categories aggressively; create sparingly.** Before creating a new
   category, check the existing list for a semantic match. Category names are
   2–5 words.
4. **Counts must be real.** Never estimate, extrapolate, or round up a tally.
   One review can yield multiple pieces; one piece increments exactly one
   category.
5. **Raw customer voice only.** Vendor blogs, SEO comparison pages, and
   marketing content are not reviews and never enter the tally.
6. **Every entry keeps receipts.** Examples carry source URLs back to the
   original issue/review (cap 6 examples per category).
7. **Skip maintainer housekeeping** — internal CI chatter, refactor notes,
   self-assigned hardening tasks yield 0 pieces.
8. **Calibrate claims to counts.** A category with count 2 from one repo is a
   signal to investigate, not a conclusion.

## Repo layout

```
pipeline/fetch_github_issues.py   # pull issues (PRs filtered) into data/raw/*.jsonl
pipeline/classify.py              # LLM classifies pieces into the taxonomy (API mode)
pipeline/tally.py                 # ranked report → stdout + reports/tally.{csv,md}
data/taxonomy.json                # THE running tally — single source of truth
data/raw/                         # fetched JSONL (gitignored, refetchable)
docs/methodology.md               # the playbook in full
docs/competitor-map.md            # field map + where the raw voice lives
web/review-miner.jsx              # browser-based miner (Claude.ai artifact version)
```

## State as of 2026-07-19

- `data/taxonomy.json` is seeded with a shakedown run: the 23 most recent
  langfuse/langfuse issues, classified by hand. Top clusters: self-hosted
  deployment breakage (4), experiments & evals workflow bugs (4), trace
  viewer renders blank (2), token/cost metrics wrong (2).
- Early insight: Langfuse's loudest recent pain is its own reliability, and
  "the trace viewer shows me nothing" appears twice in 23 issues — for a
  debugger product, trustworthy rendering of every trace IS the product.
- Issue trackers skew toward bugs; the wished_existed side lives in GitHub
  Discussions, Reddit (r/LangChain, r/LLMDevs), G2, and Discord. Those
  sources still need collection.

## Next milestones

1. Full pass: langfuse/langfuse (all ~2,738) and Arize-ai/phoenix (~5,948).
2. Remaining five repos.
3. Wish-list sources: GitHub Discussions, Reddit, G2 (paste/import path).
4. First deliverable: ranked pain/wish report for the agent-trace-debugger
   PRD — top 10 themes with counts, sources, and receipts.

## How to run (script mode)

```bash
pip install -r pipeline/requirements.txt
export GITHUB_TOKEN=...        # optional but strongly recommended (5,000 req/hr)
export ANTHROPIC_API_KEY=...   # for classify.py

python pipeline/fetch_github_issues.py --repo langfuse/langfuse --max 3000
python pipeline/classify.py            # processes everything new in data/raw/
python pipeline/tally.py               # ranked report
```

## Agent mode (Claude Code)

When asked to "continue the mining run" (or similar):

1. Run `fetch_github_issues.py` for any target repo not yet in `data/raw/`
   (or refresh stale files).
2. Classification: either run `classify.py` (needs ANTHROPIC_API_KEY), or
   classify directly — read unprocessed items from `data/raw/*.jsonl` in
   batches, apply the methodology rules above, and update
   `data/taxonomy.json` yourself (increment counts, append examples with
   URLs, add ids to `processed_ids`). Direct classification must follow rule
   3 (reuse categories) and rule 4 (real counts) strictly.
3. Run `tally.py` and report movement: new categories, biggest count gains,
   and anything relevant to the trace-debugger PRD.
4. Never fabricate a count or an example. Never tally vendor content.

Parallel agents: split by repo (one agent per raw file), but serialize writes
to `data/taxonomy.json` — it is the single source of truth.
