# The Review-Mining Playbook

Origin: run professionally for a multi-million-dollar, wildly successful
Amazon business that never interviewed a single customer — competitor review
analysis stood in for interviews entirely and drove both product development
and marketing positioning. Once the competitor list for a market was set,
every review got read and themed, with a running tally appended or
incremented per theme. This repo automates that practice.

## The loop

1. **Pick a proven market.** Existing competitors are validated demand — a
   prerequisite, not a stop sign.
2. **Collect every review you can find.** Sometimes thousands. Exhaustive
   beats sampled: the counts are the signal.
3. **Decompose.** Break each review into distinct pieces of feedback.
4. **Categorize each piece:** pain point, thing they liked, thing they wished
   existed, what they used it for.
5. **Append or increment.** New theme → new category. Known theme → count +1.
6. **Rank by mention count.** The ranked list drives everything:
   - Product: the top pains and wishes are the spec.
   - Positioning: most-mentioned themes go above the fold; less-mentioned
     points sit further down the page — a hierarchy of needs.

## Adaptation for dev tools

| Amazon era | This repo |
|---|---|
| Amazon product reviews | GitHub issues, G2/Capterra, Reddit, Discord, Discussions |
| Manual read + tally sheet | LLM decomposition + `data/taxonomy.json` |
| Product listings | Vendor blogs/SEO pages — excluded from the tally |

## Source notes

- **Issue trackers skew toward bugs** (pain_point). The wished_existed side
  concentrates in GitHub Discussions, Reddit, and review sites — collect both
  or the taxonomy lies by omission.
- Recency skew is fine for "current pain," but full-history passes reveal
  chronic themes.
