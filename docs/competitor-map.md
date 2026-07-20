# Competitor Map — Agent Observability & Debugging

As of 2026-07-19. Field: LangSmith, Langfuse (acquired by ClickHouse, Jan
2026), Braintrust, Arize Phoenix, Opik, Helicone, AgentOps, Laminar, Maxim,
W&B Weave, Galileo, Latitude, MLflow.

## Where the raw customer voice lives

| Source | Notes |
|---|---|
| GitHub issues | MINED 2026-07-19/20 — all 7 repos via public-mirror fetcher (80-83% coverage each, documented); ~9,050 issues classified |
| GitHub Discussions | Feature wishes; Langfuse's is active |
| Reddit | r/LangChain, r/LLMDevs, r/LocalLLaMA |
| G2 / Capterra | Paid-customer reviews; paste into the miner |
| Discord | Langfuse and LangChain servers; complaints in help channels |
| Hacker News | MINED 2026-07-19 (`pipeline/fetch_hn.py`) — launch/Show HN threads + topic threads, 5,168 items; vendor self-replies excluded |

## Early themes (from vendor-adjacent research — NOT tally data)

Recurring claims across comparison content, to be verified against raw voice:
pricing cliffs at scale; traces capture structure but not meaning; data
models retrofitted from request/response monitoring; framework lock-in;
trace depth itself ("failures hide in the middle of sprawling chains").

## Competitive flags for the trace-debugger PRD

- Maxim: deterministic replay (fixed-seed one-click rerun).
- LangSmith: "Polly" AI debugging assistant, platform-wide.
- Laminar: browser-agent session replay.

None of these invalidate a step-through + time-travel debugger; positioning
must state what it does that replay-a-run and explain-my-trace do not.
