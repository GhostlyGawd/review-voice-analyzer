import { useState, useRef, useEffect } from "react";

/* ------------------------------------------------------------------ */
/* Design tokens — "ledger room": cool mist paper, ink, tally greens   */
/* ------------------------------------------------------------------ */
const C = {
  bg: "#EDF1EE",
  surface: "#FFFFFF",
  surfaceAlt: "#F6F8F6",
  ink: "#17211C",
  muted: "#63706A",
  faint: "#8B968F",
  line: "#D7DED8",
  accent: "#0F7A5C",
  accentSoft: "#E2F0EA",
  danger: "#B0402C",
};
const MONO =
  "ui-monospace, 'SF Mono', 'Cascadia Mono', 'JetBrains Mono', Menlo, Consolas, monospace";
const SANS =
  "'Avenir Next', 'Segoe UI', 'Helvetica Neue', system-ui, sans-serif";

const TYPES = {
  pain_point: { label: "Pain point", short: "PAIN", color: "#B0402C", soft: "#F6E7E2" },
  wished_existed: { label: "Wished existed", short: "WISH", color: "#A97614", soft: "#F6EEDC" },
  liked: { label: "Liked", short: "LIKE", color: "#0F7A5C", soft: "#E2F0EA" },
  use_case: { label: "Use case", short: "USE", color: "#4C6270", soft: "#E7EDF0" },
};

const PRESETS = [
  { repo: "Arize-ai/phoenix", label: "Arize Phoenix", approx: "5,948" },
  { repo: "langfuse/langfuse", label: "Langfuse", approx: "2,738" },
  { repo: "comet-ml/opik", label: "Opik", approx: "697" },
  { repo: "langchain-ai/langsmith-sdk", label: "LangSmith SDK", approx: "607" },
  { repo: "AgentOps-AI/agentops", label: "AgentOps", approx: "444" },
  { repo: "Helicone/helicone", label: "Helicone", approx: "280" },
  { repo: "lmnr-ai/lmnr", label: "Laminar", approx: "133" },
];

const STORE_KEY = "miner-state-v2";
const BATCH_SIZE = 6;

/* ------------------------------------------------------------------ */
/* Helpers                                                             */
/* ------------------------------------------------------------------ */
function hashText(s) {
  let h = 0;
  for (let i = 0; i < s.length; i++) {
    h = (h << 5) - h + s.charCodeAt(i);
    h |= 0;
  }
  return Math.abs(h).toString(36);
}
const normKey = (t, c) => t + "|" + c.trim().toLowerCase();

function csvEscape(v) {
  const s = String(v == null ? "" : v);
  return '"' + s.replace(/"/g, '""') + '"';
}

/* ------------------------------------------------------------------ */
/* Component                                                           */
/* ------------------------------------------------------------------ */
export default function ReviewMiner() {
  // sources
  const [selected, setSelected] = useState(() => new Set(["langfuse/langfuse"]));
  const [customRepo, setCustomRepo] = useState("");
  const [customRepos, setCustomRepos] = useState([]);
  const [token, setToken] = useState("");
  const [maxPerRepo, setMaxPerRepo] = useState(250);
  const [pasted, setPasted] = useState("");

  // data
  const [items, setItems] = useState([]); // in-memory only (re-fetchable)
  const [taxonomy, setTaxonomy] = useState({});
  const [processed, setProcessed] = useState(() => new Set());
  const [pieces, setPieces] = useState(0);

  // machinery
  const [fetching, setFetching] = useState(false);
  const [mining, setMining] = useState(false);
  const [status, setStatus] = useState("");
  const [error, setError] = useState("");
  const [loaded, setLoaded] = useState(false);

  // board controls
  const [filterType, setFilterType] = useState("all");
  const [filterSource, setFilterSource] = useState("all");
  const [query, setQuery] = useState("");
  const [expanded, setExpanded] = useState(null);
  const [confirmClear, setConfirmClear] = useState(false);

  // refs to avoid stale closures inside the mining loop
  const miningRef = useRef(false);
  const taxRef = useRef({});
  const procRef = useRef(new Set());
  const piecesRef = useRef(0);

  /* ---------------- persistence ---------------- */
  useEffect(() => {
    (async () => {
      try {
        const res = await window.storage.get(STORE_KEY);
        if (res && res.value) {
          const s = JSON.parse(res.value);
          taxRef.current = s.taxonomy || {};
          procRef.current = new Set(s.processed || []);
          piecesRef.current = s.pieces || 0;
          setTaxonomy(taxRef.current);
          setProcessed(new Set(procRef.current));
          setPieces(piecesRef.current);
        }
      } catch (e) {
        // no saved state yet — start fresh
      }
      setLoaded(true);
    })();
  }, []);

  async function persist() {
    try {
      await window.storage.set(
        STORE_KEY,
        JSON.stringify({
          taxonomy: taxRef.current,
          processed: Array.from(procRef.current),
          pieces: piecesRef.current,
        })
      );
    } catch (e) {
      setError("Saving progress failed — mining continues, but state may not persist.");
    }
  }

  /* ---------------- fetching ---------------- */
  async function fetchRepo(repo, cap) {
    const out = [];
    let page = 1;
    while (out.length < cap) {
      const headers = { Accept: "application/vnd.github+json" };
      if (token.trim()) headers.Authorization = "Bearer " + token.trim();
      const res = await fetch(
        "https://api.github.com/repos/" +
          repo +
          "/issues?state=all&per_page=100&page=" +
          page,
        { headers }
      );
      if (res.status === 403 || res.status === 429) {
        throw new Error(
          "GitHub rate limit hit on " +
            repo +
            ". Add a personal access token below (5,000 requests/hr) or wait an hour."
        );
      }
      if (!res.ok) {
        throw new Error("GitHub returned " + res.status + " for " + repo + " — check the repo name.");
      }
      const data = await res.json();
      if (!Array.isArray(data) || data.length === 0) break;
      for (const it of data) {
        if (it.pull_request) continue;
        out.push({
          id: repo + "#" + it.number,
          source: repo,
          title: it.title || "",
          body: (it.body || "").slice(0, 1200),
          url: it.html_url,
        });
      }
      if (data.length < 100) break;
      page++;
    }
    return out.slice(0, cap);
  }

  function pastedItems() {
    const blocks = pasted
      .split(/\n\s*\n/)
      .map((b) => b.trim())
      .filter((b) => b.length > 20);
    return blocks.map((b) => ({
      id: "paste-" + hashText(b),
      source: "pasted",
      title: b.slice(0, 80),
      body: b.slice(0, 1200),
      url: null,
    }));
  }

  async function handleFetch() {
    setError("");
    setFetching(true);
    const collected = [];
    try {
      const repos = [...Array.from(selected), ...customRepos];
      for (const repo of repos) {
        setStatus("Fetching issues from " + repo + "…");
        const got = await fetchRepo(repo, maxPerRepo);
        collected.push(...got);
        setStatus("Fetched " + collected.length + " issues so far…");
      }
      collected.push(...pastedItems());
      // de-dupe by id
      const seen = new Set();
      const unique = collected.filter((it) => {
        if (seen.has(it.id)) return false;
        seen.add(it.id);
        return true;
      });
      setItems(unique);
      const fresh = unique.filter((it) => !procRef.current.has(it.id)).length;
      setStatus(
        unique.length +
          " items loaded · " +
          fresh +
          " not yet mined" +
          (unique.length - fresh > 0 ? " · " + (unique.length - fresh) + " already tallied (will be skipped)" : "")
      );
    } catch (e) {
      setError(e.message || "Fetching failed.");
      if (collected.length) setItems(collected);
    }
    setFetching(false);
  }

  /* ---------------- mining ---------------- */
  function categoryDigest() {
    const byType = {};
    for (const key of Object.keys(taxRef.current)) {
      const e = taxRef.current[key];
      if (!byType[e.type]) byType[e.type] = [];
      byType[e.type].push(e.category);
    }
    const lines = [];
    for (const t of Object.keys(byType)) {
      lines.push(TYPES[t].label + ": " + byType[t].slice(0, 60).join("; "));
    }
    return lines.join("\n");
  }

  async function classifyBatch(batch) {
    const payload = batch
      .map((it, i) => "#" + i + " [" + it.source + "] " + it.title + "\n" + it.body)
      .join("\n---\n");
    const cats = categoryDigest();
    const prompt =
      "You are a product researcher doing competitor review mining for AI-agent observability and debugging tools.\n\n" +
      "Existing categories — REUSE these exact names when a piece matches; only create a new category when nothing fits:\n" +
      (cats || "(none yet)") +
      "\n\nBreak each item below into distinct feedback pieces. For each piece assign:\n" +
      '- "t": one of pain_point | wished_existed | liked | use_case (bug reports and complaints are pain_point; feature requests are wished_existed)\n' +
      '- "c": a category name, 2-5 words, reused from the list above when semantically equivalent\n' +
      '- "n": a note summarizing the piece, max 12 words\n\n' +
      "Skip boilerplate, templates, greetings, and maintainer replies. An item may yield 0 pieces.\n\n" +
      'Respond ONLY with a JSON array, no markdown fences, shaped exactly like:\n' +
      '[{"i":0,"p":[{"t":"pain_point","c":"category name","n":"short note"}]}]\n\n' +
      "Items:\n" +
      payload;

    const res = await fetch("https://api.anthropic.com/v1/messages", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        model: "claude-sonnet-4-6",
        max_tokens: 1000,
        messages: [{ role: "user", content: prompt }],
      }),
    });
    const data = await res.json();
    const text = (data.content || [])
      .filter((b) => b.type === "text")
      .map((b) => b.text)
      .join("\n");
    const clean = text.replace(/```json|```/g, "").trim();
    const start = clean.indexOf("[");
    const end = clean.lastIndexOf("]");
    if (start === -1 || end === -1) throw new Error("Classifier returned unparseable output.");
    return JSON.parse(clean.slice(start, end + 1));
  }

  function mergeResults(batch, results) {
    let added = 0;
    for (const r of results) {
      const item = batch[r.i];
      if (!item || !Array.isArray(r.p)) continue;
      for (const p of r.p) {
        if (!p || !TYPES[p.t] || !p.c) continue;
        const key = normKey(p.t, p.c);
        const entry =
          taxRef.current[key] || {
            type: p.t,
            category: p.c.trim(),
            count: 0,
            examples: [],
            sources: {},
          };
        entry.count++;
        entry.sources[item.source] = (entry.sources[item.source] || 0) + 1;
        if (entry.examples.length < 6) {
          entry.examples.push({ n: p.n || "", source: item.source, url: item.url });
        }
        taxRef.current[key] = entry;
        added++;
      }
    }
    piecesRef.current += added;
  }

  async function startMining() {
    setError("");
    miningRef.current = true;
    setMining(true);
    const queue = items.filter((it) => !procRef.current.has(it.id));
    let done = 0;
    for (let i = 0; i < queue.length; i += BATCH_SIZE) {
      if (!miningRef.current) break;
      const batch = queue.slice(i, i + BATCH_SIZE);
      setStatus(
        "Mining… " + (done + batch.length) + " / " + queue.length + " new items this run"
      );
      try {
        const results = await classifyBatch(batch);
        mergeResults(batch, results);
      } catch (e) {
        // one bad batch shouldn't kill the run — note it and continue
        setError("A batch failed (" + (e.message || "unknown error") + "). Continuing.");
      }
      for (const it of batch) procRef.current.add(it.id);
      done += batch.length;
      setTaxonomy({ ...taxRef.current });
      setProcessed(new Set(procRef.current));
      setPieces(piecesRef.current);
      await persist();
    }
    miningRef.current = false;
    setMining(false);
    setStatus(done > 0 ? "Run complete — " + done + " items mined this session." : "Nothing new to mine. Fetch more sources.");
  }

  function pauseMining() {
    miningRef.current = false;
    setMining(false);
    setStatus("Paused. Progress is saved — press Start to resume.");
  }

  /* ---------------- export & clear ---------------- */
  function exportCsv() {
    const rows = [["type", "category", "mentions", "sources", "example_notes"]];
    const entries = Object.values(taxRef.current).sort((a, b) => b.count - a.count);
    for (const e of entries) {
      rows.push([
        TYPES[e.type].label,
        e.category,
        e.count,
        Object.entries(e.sources)
          .map(([s, n]) => s + " (" + n + ")")
          .join("; "),
        e.examples.map((x) => x.n).join(" | "),
      ]);
    }
    const csv = rows.map((r) => r.map(csvEscape).join(",")).join("\n");
    const blob = new Blob([csv], { type: "text/csv" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = "pain-tally.csv";
    a.click();
    URL.revokeObjectURL(a.href);
  }

  async function clearAll() {
    taxRef.current = {};
    procRef.current = new Set();
    piecesRef.current = 0;
    setTaxonomy({});
    setProcessed(new Set());
    setPieces(0);
    setConfirmClear(false);
    setStatus("Tally cleared.");
    try {
      await window.storage.set(STORE_KEY, JSON.stringify({ taxonomy: {}, processed: [], pieces: 0 }));
    } catch (e) {}
  }

  /* ---------------- derived ---------------- */
  const entries = Object.values(taxonomy);
  const allSources = Array.from(
    new Set(entries.flatMap((e) => Object.keys(e.sources)))
  ).sort();
  const visible = entries
    .filter((e) => filterType === "all" || e.type === filterType)
    .filter((e) => filterSource === "all" || e.sources[filterSource])
    .filter(
      (e) =>
        !query.trim() ||
        e.category.toLowerCase().includes(query.trim().toLowerCase()) ||
        e.examples.some((x) => (x.n || "").toLowerCase().includes(query.trim().toLowerCase()))
    )
    .sort((a, b) => b.count - a.count);
  const maxCount = visible.length ? visible[0].count : 1;
  const unprocessedCount = items.filter((it) => !processed.has(it.id)).length;

  /* ---------------- UI bits ---------------- */
  const panel = {
    background: C.surface,
    border: "1px solid " + C.line,
    borderRadius: 10,
  };
  const eyebrow = {
    fontFamily: MONO,
    fontSize: 11,
    letterSpacing: "0.14em",
    color: C.muted,
  };
  const inputStyle = {
    fontFamily: MONO,
    fontSize: 13,
    color: C.ink,
    background: C.surfaceAlt,
    border: "1px solid " + C.line,
    borderRadius: 6,
    padding: "8px 10px",
    outline: "none",
    width: "100%",
  };
  const btn = (primary) => ({
    fontFamily: MONO,
    fontSize: 13,
    letterSpacing: "0.04em",
    padding: "10px 18px",
    borderRadius: 7,
    cursor: "pointer",
    border: "1px solid " + (primary ? C.accent : C.line),
    background: primary ? C.accent : C.surface,
    color: primary ? "#fff" : C.ink,
  });

  function Stat({ label, value }) {
    return (
      <div className="flex flex-col">
        <span style={{ fontFamily: MONO, fontSize: 26, fontWeight: 600, color: C.ink, fontVariantNumeric: "tabular-nums" }}>
          {value.toLocaleString()}
        </span>
        <span style={eyebrow}>{label}</span>
      </div>
    );
  }

  function Tally({ count, color }) {
    const ticks = Math.max(1, Math.round((count / maxCount) * 34));
    return (
      <span
        aria-hidden="true"
        style={{
          fontFamily: MONO,
          fontSize: 13,
          letterSpacing: 2,
          color,
          whiteSpace: "nowrap",
          overflow: "hidden",
        }}
      >
        {"|".repeat(ticks)}
      </span>
    );
  }

  if (!loaded) {
    return (
      <div className="min-h-screen flex items-center justify-center" style={{ background: C.bg }}>
        <span style={{ fontFamily: MONO, color: C.muted }}>Opening the ledger…</span>
      </div>
    );
  }

  return (
    <div className="min-h-screen w-full" style={{ background: C.bg, color: C.ink, fontFamily: SANS }}>
      <div className="mx-auto px-4 py-8" style={{ maxWidth: 980 }}>
        {/* ---------- header ---------- */}
        <div className="mb-6">
          <div style={eyebrow}>COMPETITOR REVIEW MINING · AGENT OBSERVABILITY</div>
          <h1
            style={{
              fontFamily: MONO,
              fontSize: 34,
              fontWeight: 700,
              letterSpacing: "0.06em",
              margin: "6px 0 0 0",
            }}
          >
            THE TALLY BOARD
          </h1>
          <p style={{ color: C.muted, fontSize: 14, marginTop: 6, maxWidth: 560 }}>
            Every issue gets read, broken into pieces, categorized, and counted.
            Counts persist between sessions — keep feeding it sources.
          </p>
        </div>

        {/* ---------- stat strip ---------- */}
        <div className="flex flex-wrap gap-8 mb-6 px-5 py-4" style={panel}>
          <Stat label="ITEMS LOADED" value={items.length} />
          <Stat label="ITEMS MINED" value={processed.size} />
          <Stat label="PIECES TALLIED" value={pieces} />
          <Stat label="CATEGORIES" value={entries.length} />
        </div>

        {/* ---------- 1 · sources ---------- */}
        <div className="mb-4 p-5" style={panel}>
          <div style={eyebrow}>1 · SOURCES</div>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 mt-3">
            {PRESETS.map((p) => {
              const on = selected.has(p.repo);
              return (
                <button
                  key={p.repo}
                  onClick={() => {
                    const next = new Set(selected);
                    on ? next.delete(p.repo) : next.add(p.repo);
                    setSelected(next);
                  }}
                  className="flex items-center justify-between px-3 py-2 text-left"
                  style={{
                    border: "1px solid " + (on ? C.accent : C.line),
                    background: on ? C.accentSoft : C.surfaceAlt,
                    borderRadius: 7,
                    cursor: "pointer",
                  }}
                >
                  <span>
                    <span style={{ fontSize: 14, fontWeight: 600 }}>{p.label}</span>
                    <span style={{ fontFamily: MONO, fontSize: 11, color: C.muted, marginLeft: 8 }}>
                      {p.repo}
                    </span>
                  </span>
                  <span style={{ fontFamily: MONO, fontSize: 11, color: on ? C.accent : C.faint }}>
                    ~{p.approx}
                  </span>
                </button>
              );
            })}
          </div>

          <div className="flex flex-wrap gap-2 mt-3 items-center">
            <div style={{ flex: "1 1 220px" }}>
              <input
                style={inputStyle}
                placeholder="Add another repo — owner/name"
                value={customRepo}
                onChange={(e) => setCustomRepo(e.target.value)}
              />
            </div>
            <button
              style={btn(false)}
              onClick={() => {
                const v = customRepo.trim();
                if (v && v.includes("/") && !customRepos.includes(v)) {
                  setCustomRepos([...customRepos, v]);
                  setCustomRepo("");
                }
              }}
            >
              Add repo
            </button>
            {customRepos.map((r) => (
              <span
                key={r}
                style={{
                  fontFamily: MONO,
                  fontSize: 12,
                  background: C.accentSoft,
                  color: C.accent,
                  padding: "4px 10px",
                  borderRadius: 999,
                }}
              >
                {r}
                <button
                  onClick={() => setCustomRepos(customRepos.filter((x) => x !== r))}
                  style={{ marginLeft: 6, cursor: "pointer", background: "none", border: "none", color: C.accent }}
                  aria-label={"Remove " + r}
                >
                  ×
                </button>
              </span>
            ))}
          </div>

          <textarea
            style={{ ...inputStyle, marginTop: 10, minHeight: 72, fontFamily: SANS }}
            placeholder="Or paste raw reviews here (G2, Reddit threads, Discord…) — one review per blank-line-separated block"
            value={pasted}
            onChange={(e) => setPasted(e.target.value)}
          />

          <div className="flex flex-wrap gap-2 mt-3 items-center">
            <div style={{ flex: "1 1 220px" }}>
              <input
                style={inputStyle}
                type="password"
                placeholder="GitHub token — optional, raises rate limit to 5,000/hr"
                value={token}
                onChange={(e) => setToken(e.target.value)}
              />
            </div>
            <select
              style={{ ...inputStyle, width: "auto" }}
              value={maxPerRepo}
              onChange={(e) => setMaxPerRepo(Number(e.target.value))}
            >
              <option value={100}>100 issues / repo</option>
              <option value={250}>250 issues / repo</option>
              <option value={500}>500 issues / repo</option>
              <option value={1000}>1,000 issues / repo</option>
              <option value={9999}>All issues</option>
            </select>
            <button style={btn(true)} onClick={handleFetch} disabled={fetching}>
              {fetching ? "Fetching…" : "Fetch issues"}
            </button>
          </div>
          <p style={{ fontFamily: MONO, fontSize: 11, color: C.faint, marginTop: 8 }}>
            Without a token, GitHub allows ~60 requests/hr (~6,000 issues). The token stays in this
            session only — it is never saved.
          </p>
        </div>

        {/* ---------- 2 · mine ---------- */}
        <div className="mb-4 p-5" style={panel}>
          <div style={eyebrow}>2 · MINE</div>
          <div className="flex flex-wrap items-center gap-3 mt-3">
            <button
              style={btn(!mining)}
              onClick={mining ? pauseMining : startMining}
              disabled={items.length === 0 || (unprocessedCount === 0 && !mining)}
            >
              {mining ? "Pause" : "Start mining"}
            </button>
            <span style={{ fontFamily: MONO, fontSize: 13, color: C.muted }}>
              {items.length === 0
                ? "Fetch sources first."
                : unprocessedCount + " items waiting · batches of " + BATCH_SIZE}
            </span>
          </div>
          {items.length > 0 && (
            <div className="mt-3" style={{ height: 6, background: C.surfaceAlt, borderRadius: 999, overflow: "hidden", border: "1px solid " + C.line }}>
              <div
                style={{
                  height: "100%",
                  width:
                    Math.min(
                      100,
                      Math.round(
                        (items.filter((it) => processed.has(it.id)).length / items.length) * 100
                      )
                    ) + "%",
                  background: C.accent,
                  transition: "width 300ms ease",
                }}
              />
            </div>
          )}
          {status && (
            <p style={{ fontFamily: MONO, fontSize: 12, color: C.muted, marginTop: 8 }}>{status}</p>
          )}
          {error && (
            <p style={{ fontFamily: MONO, fontSize: 12, color: C.danger, marginTop: 4 }}>{error}</p>
          )}
        </div>

        {/* ---------- 3 · tally board ---------- */}
        <div className="p-5" style={panel}>
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div style={eyebrow}>3 · TALLY BOARD</div>
            <div className="flex gap-2">
              <button style={btn(false)} onClick={exportCsv} disabled={entries.length === 0}>
                Export CSV
              </button>
              {confirmClear ? (
                <>
                  <button style={{ ...btn(false), color: C.danger, borderColor: C.danger }} onClick={clearAll}>
                    Really clear
                  </button>
                  <button style={btn(false)} onClick={() => setConfirmClear(false)}>
                    Keep
                  </button>
                </>
              ) : (
                <button style={btn(false)} onClick={() => setConfirmClear(true)} disabled={entries.length === 0}>
                  Clear all data
                </button>
              )}
            </div>
          </div>

          {/* filters */}
          <div className="flex flex-wrap gap-2 mt-4">
            {[["all", "All"], ...Object.entries(TYPES).map(([k, v]) => [k, v.label])].map(
              ([k, label]) => (
                <button
                  key={k}
                  onClick={() => setFilterType(k)}
                  style={{
                    fontFamily: MONO,
                    fontSize: 12,
                    padding: "5px 12px",
                    borderRadius: 999,
                    cursor: "pointer",
                    border: "1px solid " + (filterType === k ? C.ink : C.line),
                    background: filterType === k ? C.ink : C.surface,
                    color: filterType === k ? "#fff" : C.muted,
                  }}
                >
                  {label}
                </button>
              )
            )}
            {allSources.length > 1 && (
              <select
                style={{ ...inputStyle, width: "auto", padding: "5px 10px", fontSize: 12 }}
                value={filterSource}
                onChange={(e) => setFilterSource(e.target.value)}
              >
                <option value="all">All sources</option>
                {allSources.map((s) => (
                  <option key={s} value={s}>
                    {s}
                  </option>
                ))}
              </select>
            )}
            <div style={{ flex: "1 1 160px" }}>
              <input
                style={{ ...inputStyle, padding: "5px 10px", fontSize: 12 }}
                placeholder="Search categories"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
              />
            </div>
          </div>

          {/* rows */}
          {visible.length === 0 ? (
            <p style={{ color: C.muted, fontSize: 14, marginTop: 20 }}>
              No tallies yet. Fetch sources above and start mining — every piece of feedback lands
              here, counted.
            </p>
          ) : (
            <div className="mt-4">
              {visible.map((e, idx) => {
                const t = TYPES[e.type];
                const key = normKey(e.type, e.category);
                const open = expanded === key;
                return (
                  <div key={key} style={{ borderTop: "1px solid " + C.line }}>
                    <button
                      onClick={() => setExpanded(open ? null : key)}
                      className="w-full flex items-center gap-3 py-3 text-left"
                      style={{ background: "none", border: "none", cursor: "pointer" }}
                    >
                      <span style={{ fontFamily: MONO, fontSize: 12, color: C.faint, width: 28, flexShrink: 0 }}>
                        {String(idx + 1).padStart(2, "0")}
                      </span>
                      <span
                        style={{
                          fontFamily: MONO,
                          fontSize: 10,
                          letterSpacing: "0.1em",
                          color: t.color,
                          background: t.soft,
                          padding: "3px 8px",
                          borderRadius: 4,
                          flexShrink: 0,
                        }}
                      >
                        {t.short}
                      </span>
                      <span style={{ fontSize: 14, fontWeight: 600, flexShrink: 0, maxWidth: "38%" }}>
                        {e.category}
                      </span>
                      <span className="flex-1 min-w-0">
                        <Tally count={e.count} color={t.color} />
                      </span>
                      <span
                        style={{
                          fontFamily: MONO,
                          fontSize: 20,
                          fontWeight: 700,
                          fontVariantNumeric: "tabular-nums",
                          flexShrink: 0,
                        }}
                      >
                        {e.count}
                      </span>
                    </button>
                    {open && (
                      <div className="pb-4" style={{ paddingLeft: 40 }}>
                        <div style={{ fontFamily: MONO, fontSize: 11, color: C.muted, marginBottom: 6 }}>
                          {Object.entries(e.sources)
                            .map(([s, n]) => s + " × " + n)
                            .join(" · ")}
                        </div>
                        {e.examples.map((x, i) => (
                          <div key={i} style={{ fontSize: 13, color: C.ink, padding: "4px 0" }}>
                            <span style={{ color: t.color, fontFamily: MONO }}>— </span>
                            {x.n}
                            {x.url && (
                              <a
                                href={x.url}
                                target="_blank"
                                rel="noreferrer"
                                style={{ fontFamily: MONO, fontSize: 11, color: C.accent, marginLeft: 8 }}
                              >
                                open ↗
                              </a>
                            )}
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>

        <p style={{ fontFamily: MONO, fontSize: 11, color: C.faint, marginTop: 14, textAlign: "center" }}>
          Fetch → mine → tally. Your counts survive refreshes; raw issues are re-fetched each session.
        </p>
      </div>
    </div>
  );
}
