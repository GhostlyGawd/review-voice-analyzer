# Review Voice Analyzer

Turns raw customer feedback (GitHub issues, reviews, forum threads) into a
ranked, counted taxonomy of pain points, wishes, likes, and use cases —
an automated version of a review-mining playbook proven on Amazon.

**Read `CLAUDE.md` first** — it carries the full context, methodology rules,
and current state. It is written for Claude Code agents but is the best
human overview too.

## Quickstart

```bash
pip install -r pipeline/requirements.txt
export GITHUB_TOKEN=...        # recommended: 5,000 req/hr vs 60 anonymous
export ANTHROPIC_API_KEY=...   # https://console.anthropic.com

python pipeline/fetch_github_issues.py --repo langfuse/langfuse --max 3000
python pipeline/classify.py
python pipeline/tally.py
```

`data/taxonomy.json` is the single source of truth and is safe to interrupt —
classification resumes where it left off.

## With Claude Code

Open this repo and say: **"Read CLAUDE.md and continue the mining run."**
Agents can run the scripts or classify batches directly per the rules in
CLAUDE.md.

## Browser version

`web/review-miner.jsx` is a Claude.ai artifact ("The Tally Board") that runs
the same loop client-side — useful for pasting G2/Reddit content without any
API keys.

## Current state

Seeded with a 23-issue Langfuse shakedown (2026-07-19): 22 pieces across 12
categories. See `reports/tally.md`.
