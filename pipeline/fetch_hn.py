#!/usr/bin/env python3
"""Fetch Hacker News voice on the competitor field into data/raw/hn.jsonl.

Uses the Algolia HN Search API (no key needed):
  - keyword search over stories and comments for each competitor/topic query
  - full comment-tree pulls for on-topic stories, so in-thread replies that
    never name the product are still captured (rule 1: exhaustive per source)

Ambiguous names (phoenix, weave, galileo, ...) require a co-occurring
context word before an item is kept. Vendor self-replies are NOT filtered
here — that judgment happens at classification time (rule 5).
"""
import html, json, os, re, sys, time
import requests

RAW_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "raw")
API = "https://hn.algolia.com/api/v1"
SOURCE = "hn"
BODY_CAP = 1200
THREAD_CAP = 200          # max full comment trees to pull (logged if hit)
PAGE_CAP = 20             # algolia pagination guard per query

UNAMBIGUOUS = ["langfuse", "langsmith", "helicone", "opik", "agentops",
               "lmnr", "arize", "openllmetry"]
# name -> at least one of these must co-occur (lowercase substring match)
AMBIGUOUS = {
    "phoenix":   ["arize", "llm", "trace", "tracing", "eval", "observab",
                  "agent", "langchain", "openinference", "prompt"],
    "braintrust": ["llm", "eval", "prompt", "agent", "observab", "ai",
                   "braintrust.dev", "braintrustdata"],
    "laminar":   ["llm", "agent", "trace", "observab", "lmnr", "ai"],
    "weave":     ["wandb", "w&b", "weights", "llm", "trace", "agent"],
    "galileo":   ["llm", "eval", "hallucin", "observab", "agent", "rungalileo"],
    "maxim":     ["llm", "agent", "eval", "observab", "getmaxim"],
    "latitude":  ["prompt", "llm", "latitude.so", "agent", "eval"],
}
TOPICS = ["llm observability", "agent observability", "llm tracing",
          "agent debugging", "ai agent debugging", "llm monitoring",
          "agent traces", "llm evals"]

TAG_RE = re.compile(r"<[^>]+>")
WS_RE = re.compile(r"\s+")

# Full comment trees are pulled only when the story TITLE is about a vendor
# or the topic space — text-only matches proved to be incidental mentions
# inside unrelated megathreads.
VENDOR_TITLE_RE = re.compile(
    r"\b(langfuse|langsmith|helicone|opik|agentops|lmnr|arize|openllmetry|"
    r"phoenix|braintrust|laminar|weave|galileo|maxim|latitude)\b", re.I)
TOPIC_TITLE_RE = re.compile(
    r"(?=.*\b(llms?|agents?|ai)\b)"
    r"(?=.*\b(observab\w*|monitor\w*|trac(?:e|es|ing)|debug\w*|evals?\w*)\b)",
    re.I)
HIRING_RE = re.compile(r"who wants to be hired|who is hiring|freelancer\? seeking", re.I)

def title_wants_tree(query, title, text):
    if not title:
        return False
    if VENDOR_TITLE_RE.search(title):
        # ambiguous names still need their context words somewhere
        m = VENDOR_TITLE_RE.search(title).group(1).lower()
        if m in AMBIGUOUS:
            combined = f"{title} {text}".lower()
            return any(w in combined for w in AMBIGUOUS[m])
        return True
    return bool(TOPIC_TITLE_RE.search(title))

def clean(text):
    if not text:
        return ""
    return WS_RE.sub(" ", TAG_RE.sub(" ", html.unescape(text))).strip()

def get(path, params=None, tries=3):
    for attempt in range(tries):
        r = requests.get(f"{API}/{path}", params=params, timeout=30)
        if r.status_code == 429:
            time.sleep(2 ** (attempt + 1))
            continue
        r.raise_for_status()
        return r.json()
    sys.exit(f"Rate limited by Algolia on {path} after {tries} tries.")

def on_topic(query, *texts):
    """Require every query word literally (word-boundary, optional plural) in
    the item's own text — Algolia's typo tolerance otherwise matches
    arize→arise, maxim→maximum, tracing→trading, etc."""
    combined = " ".join(clean(t).lower() for t in texts if t)
    for w in query.lower().split():
        base = re.escape(w[:-1] if w.endswith("s") else w)
        if not re.search(rf"\b{base}s?\b", combined):
            return False
    if query in AMBIGUOUS:
        return any(w in combined for w in AMBIGUOUS[query])
    return True

def search(query, tag):
    """Yield all hits for query/tag via search_by_date pagination."""
    page = 0
    while page < PAGE_CAP:
        data = get("search_by_date",
                   {"query": query, "tags": tag, "hitsPerPage": 1000, "page": page})
        for h in data.get("hits", []):
            yield h
        page += 1
        if page >= data.get("nbPages", 0):
            break
        time.sleep(0.25)

def story_item(hit_or_node, oid, title, text, url_field, created):
    body = clean(text) or (url_field or "")
    return {
        "id": f"hn#{oid}", "source": SOURCE, "state": "story",
        "title": title or "", "body": body[:BODY_CAP],
        "url": f"https://news.ycombinator.com/item?id={oid}",
        "created_at": created,
    }

def comment_item(oid, story_title, text, created):
    return {
        "id": f"hn#{oid}", "source": SOURCE, "state": "comment",
        "title": f"[re: {story_title or 'HN thread'}]",
        "body": clean(text)[:BODY_CAP],
        "url": f"https://news.ycombinator.com/item?id={oid}",
        "created_at": created,
    }

def walk(node, story_title, out, seen):
    for child in node.get("children") or []:
        oid = str(child.get("id"))
        text = clean(child.get("text"))
        if text and not child.get("deleted") and oid not in seen:
            seen.add(oid)
            out.append(comment_item(oid, story_title, child.get("text"),
                                    child.get("created_at")))
        walk(child, story_title, out, seen)

def main():
    items, seen, thread_candidates = [], set(), {}
    queries = UNAMBIGUOUS + list(AMBIGUOUS) + TOPICS
    for q in queries:
        s_hits = c_hits = 0
        for hit in search(q, "story"):
            oid = str(hit["objectID"])
            title, text = hit.get("title") or "", hit.get("story_text") or ""
            if not on_topic(q, title, text):
                continue
            s_hits += 1
            # link posts with no text carry no customer voice of their own
            keep_story = len(clean(text)) > 80 or VENDOR_TITLE_RE.search(title or "")
            if oid not in seen and keep_story:
                seen.add(oid)
                items.append(story_item(hit, oid, title, text,
                                        hit.get("url"), hit.get("created_at")))
            n = hit.get("num_comments") or 0
            if n > 0 and title_wants_tree(q, title, text):
                thread_candidates[oid] = max(thread_candidates.get(oid, 0), n)
        for hit in search(q, "comment"):
            oid = str(hit["objectID"])
            text = hit.get("comment_text") or ""
            if HIRING_RE.search(hit.get("story_title") or ""):
                continue  # résumé skill-lists in job threads are not feedback
            if not on_topic(q, text, hit.get("story_title")):
                continue
            c_hits += 1
            if oid not in seen and clean(text):
                seen.add(oid)
                items.append(comment_item(oid, hit.get("story_title"),
                                          text, hit.get("created_at")))
        print(f"  '{q}': {s_hits} stories, {c_hits} comments", flush=True)
        time.sleep(0.25)

    ranked = sorted(thread_candidates.items(), key=lambda kv: -kv[1])
    if len(ranked) > THREAD_CAP:
        dropped = len(ranked) - THREAD_CAP
        print(f"NOTE: pulling top {THREAD_CAP} threads by comment count; "
              f"skipping {dropped} smaller threads (not silent — rerun with "
              f"higher THREAD_CAP for full trees).", flush=True)
    pulled = 0
    for oid, n in ranked[:THREAD_CAP]:
        tree = get(f"items/{oid}")
        if not tree.get("title") or tree.get("title", "").strip("[]").lower() in ("dead", "flagged"):
            continue  # story died since the search hit; skip its tree
        walk(tree, tree.get("title"), items, seen)
        pulled += 1
        if pulled % 25 == 0:
            print(f"  threads: {pulled}/{min(len(ranked), THREAD_CAP)}, "
                  f"{len(items)} items total", flush=True)
        time.sleep(0.25)

    os.makedirs(RAW_DIR, exist_ok=True)
    path = os.path.join(RAW_DIR, "hn.jsonl")
    with open(path, "w") as f:
        for it in items:
            f.write(json.dumps(it) + "\n")
    stories = sum(1 for i in items if i["state"] == "story")
    print(f"Wrote {len(items)} items ({stories} stories, "
          f"{len(items) - stories} comments) → {path}", flush=True)

if __name__ == "__main__":
    main()
