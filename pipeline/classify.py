#!/usr/bin/env python3
"""Classify raw items into the running taxonomy via the Claude API.

Reads data/raw/*.jsonl, skips ids already in taxonomy processed_ids,
classifies in batches, and updates data/taxonomy.json after every batch
(safe to interrupt and resume).

Docs: https://docs.claude.com/en/api/overview
"""
import glob, json, os, sys
from anthropic import Anthropic

HERE = os.path.dirname(__file__)
RAW_DIR = os.path.join(HERE, "..", "data", "raw")
TAX_PATH = os.path.join(HERE, "..", "data", "taxonomy.json")
MODEL = os.environ.get("RVA_MODEL", "claude-sonnet-4-6")
BATCH = 8
TYPES = {"pain_point", "wished_existed", "liked", "use_case"}

def load_tax():
    with open(TAX_PATH) as f:
        return json.load(f)

def save_tax(tax):
    with open(TAX_PATH, "w") as f:
        json.dump(tax, f, indent=2)

def category_digest(tax):
    by_type = {}
    for e in tax["entries"]:
        by_type.setdefault(e["type"], []).append(e["category"])
    return "\n".join(f"{t}: " + "; ".join(cats[:80]) for t, cats in by_type.items())

def build_prompt(batch, tax):
    items = "\n---\n".join(
        f"#{i} [{it['source']}] {it['title']}\n{it['body']}" for i, it in enumerate(batch)
    )
    return (
        "You are a product researcher doing competitor review mining for "
        "AI-agent observability and debugging tools.\n\n"
        "Existing categories - REUSE these exact names when a piece matches; "
        "only create a new category when nothing fits:\n"
        f"{category_digest(tax) or '(none yet)'}\n\n"
        "Break each item below into distinct feedback pieces. For each piece assign:\n"
        '- "t": one of pain_point | wished_existed | liked | use_case '
        "(bug reports and complaints are pain_point; feature requests are wished_existed)\n"
        '- "c": category name, 2-5 words, reused from the list above when semantically equivalent\n'
        '- "n": a note summarizing the piece, max 12 words\n\n'
        "Skip boilerplate, templates, and maintainer housekeeping - such items yield 0 pieces.\n\n"
        "Respond ONLY with a JSON array, no markdown fences, shaped exactly like:\n"
        '[{"i":0,"p":[{"t":"pain_point","c":"category name","n":"short note"}]}]\n\n'
        f"Items:\n{items}"
    )

def merge(tax, batch, results):
    index = {(e["type"], e["category"].strip().lower()): e for e in tax["entries"]}
    added = 0
    for r in results:
        item = batch[r.get("i", -1)] if 0 <= r.get("i", -1) < len(batch) else None
        if not item or not isinstance(r.get("p"), list):
            continue
        for p in r["p"]:
            if not isinstance(p, dict) or p.get("t") not in TYPES or not p.get("c"):
                continue
            key = (p["t"], p["c"].strip().lower())
            e = index.get(key)
            if e is None:
                e = {"type": p["t"], "category": p["c"].strip(), "count": 0,
                     "sources": {}, "examples": []}
                tax["entries"].append(e)
                index[key] = e
            e["count"] += 1
            e["sources"][item["source"]] = e["sources"].get(item["source"], 0) + 1
            if len(e["examples"]) < 6:
                e["examples"].append({"note": p.get("n", ""), "url": item.get("url")})
            added += 1
    return added

def main():
    if not os.environ.get("ANTHROPIC_API_KEY"):
        sys.exit("Set ANTHROPIC_API_KEY. Get one at https://console.anthropic.com")
    client = Anthropic()
    tax = load_tax()
    done = set(tax.get("processed_ids", []))
    queue = []
    for path in sorted(glob.glob(os.path.join(RAW_DIR, "*.jsonl"))):
        with open(path) as f:
            for line in f:
                it = json.loads(line)
                if it["id"] not in done:
                    queue.append(it)
    if not queue:
        print("Nothing new to classify. Fetch more sources first.")
        return
    print(f"{len(queue)} unprocessed items. Classifying in batches of {BATCH}…")
    for i in range(0, len(queue), BATCH):
        batch = queue[i:i + BATCH]
        try:
            msg = client.messages.create(
                model=MODEL, max_tokens=1500,
                messages=[{"role": "user", "content": build_prompt(batch, tax)}],
            )
            text = "".join(b.text for b in msg.content if b.type == "text")
            text = text.replace("```json", "").replace("```", "").strip()
            results = json.loads(text[text.index("["):text.rindex("]") + 1])
            n = merge(tax, batch, results)
        except Exception as exc:  # one bad batch shouldn't kill the run
            print(f"  batch at {i} failed ({exc}); marking processed and continuing")
            n = 0
        for it in batch:
            done.add(it["id"])
        tax["processed_ids"] = sorted(done)
        save_tax(tax)
        print(f"  {min(i + BATCH, len(queue))}/{len(queue)} items · +{n} pieces "
              f"· {len(tax['entries'])} categories", flush=True)
    print("Run complete. Next: python pipeline/tally.py")

if __name__ == "__main__":
    main()
