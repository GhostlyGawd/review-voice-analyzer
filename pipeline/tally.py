#!/usr/bin/env python3
"""Print the ranked tally and write reports/tally.csv + reports/tally.md."""
import csv, json, os

HERE = os.path.dirname(__file__)
TAX_PATH = os.path.join(HERE, "..", "data", "taxonomy.json")
REPORTS = os.path.join(HERE, "..", "reports")
LABELS = {"pain_point": "PAIN", "wished_existed": "WISH",
          "liked": "LIKE", "use_case": "USE"}

def main():
    with open(TAX_PATH) as f:
        tax = json.load(f)
    entries = sorted(tax["entries"], key=lambda e: -e["count"])
    total = sum(e["count"] for e in entries)
    print(f"\n{total} pieces · {len(entries)} categories · "
          f"{len(tax.get('processed_ids', []))} items processed\n")
    for i, e in enumerate(entries, 1):
        srcs = ", ".join(f"{s}×{n}" for s, n in sorted(e["sources"].items(), key=lambda x: -x[1]))
        print(f"{i:>3}. [{LABELS[e['type']]}] {e['category']:<42} {e['count']:>4}  ({srcs})")
    os.makedirs(REPORTS, exist_ok=True)
    with open(os.path.join(REPORTS, "tally.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["rank", "type", "category", "mentions", "sources", "example_urls"])
        for i, e in enumerate(entries, 1):
            w.writerow([i, e["type"], e["category"], e["count"],
                        "; ".join(f"{s} ({n})" for s, n in e["sources"].items()),
                        " ".join(x.get("url") or "" for x in e["examples"])])
    with open(os.path.join(REPORTS, "tally.md"), "w") as f:
        f.write(f"# Tally — {total} pieces across {len(entries)} categories\n\n")
        f.write("| # | Type | Category | Mentions | Sources |\n|---|---|---|---|---|\n")
        for i, e in enumerate(entries, 1):
            srcs = ", ".join(f"{s} ×{n}" for s, n in e["sources"].items())
            f.write(f"| {i} | {LABELS[e['type']]} | {e['category']} | {e['count']} | {srcs} |\n")
    print(f"\nWrote reports/tally.csv and reports/tally.md")

if __name__ == "__main__":
    main()
