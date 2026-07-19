#!/usr/bin/env python3
"""Fetch GitHub issues from the public GH Archive mirror on ClickHouse.

For environments where api.github.com is scoped/blocked (e.g. Claude Code
remote sessions), this pulls issue title/body/state from the public
`github_events` dataset at play.clickhouse.com (anonymous, no credentials).

COVERAGE CAVEAT — this mirror has systematic gaps (whole months missing from
the dataset's ingestion). The script prints per-repo coverage against
--expected and a month histogram; decide consciously whether partial
coverage is acceptable before tallying (methodology rule 1: exhaustive
beats sampled). Use fetch_github_issues.py with a GITHUB_TOKEN wherever
the real API is reachable — this is the fallback, not the default.

Output schema matches fetch_github_issues.py exactly.
"""
import argparse, json, os, sys, time
import requests

RAW_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "raw")
ENDPOINT = "https://play.clickhouse.com/?user=play"
BODY_CAP = 1200
RANGE = 3000  # issue numbers per query chunk, keeps responses small

def q(sql, tries=3):
    for attempt in range(tries):
        r = requests.post(ENDPOINT, data=sql.encode(), timeout=120)
        if r.status_code in (429, 503):
            time.sleep(3 * (attempt + 1))
            continue
        r.raise_for_status()
        return r.text
    sys.exit(f"ClickHouse playground unavailable after {tries} tries.")

def fetch_repo(repo):
    max_num = int(q(
        f"SELECT max(number) FROM github_events WHERE repo_name='{repo}' "
        f"AND event_type='IssuesEvent' FORMAT TSV").strip() or 0)
    items = []
    for lo in range(1, max_num + 1, RANGE):
        hi = lo + RANGE - 1
        rows = q(
            "SELECT number, argMax(title, created_at) AS title, "
            f"argMax(substring(body, 1, {BODY_CAP}), created_at) AS body, "
            "argMax(state, created_at) AS state, min(created_at) AS created "
            f"FROM github_events WHERE repo_name='{repo}' "
            "AND event_type='IssuesEvent' "
            f"AND number BETWEEN {lo} AND {hi} "
            "GROUP BY number ORDER BY number FORMAT JSONEachRow")
        for line in rows.splitlines():
            row = json.loads(line)
            state = row["state"] if row["state"] in ("open", "closed") else "open"
            items.append({
                "id": f"{repo}#{row['number']}",
                "source": repo,
                "state": state,
                "title": row["title"] or "",
                "body": (row["body"] or "")[:BODY_CAP],
                "url": f"https://github.com/{repo}/issues/{row['number']}",
                "created_at": row["created"].replace(" ", "T") + "Z",
            })
        time.sleep(0.5)
    return items

def coverage_report(repo, items, expected):
    from collections import Counter
    months = Counter(it["created_at"][:7] for it in items)
    got = len(items)
    print(f"  {repo}: {got} issues with title+body from mirror", flush=True)
    if expected:
        print(f"  coverage vs expected ~{expected}: {100 * got / expected:.0f}% "
              f"— MIRROR HAS GAPS, do not treat as exhaustive without a "
              f"true-up pass", flush=True)
    if months:
        first, last = min(months), max(months)
        print(f"  span {first} → {last}; sparsest recent months: "
              + ", ".join(f"{m}×{n}" for m, n in sorted(months.items())[-4:]),
              flush=True)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", action="append", required=True, help="owner/name (repeatable)")
    ap.add_argument("--expected", type=int, default=0,
                    help="known real issue count, for the coverage report")
    args = ap.parse_args()
    os.makedirs(RAW_DIR, exist_ok=True)
    for repo in args.repo:
        print(f"Fetching {repo} from GH Archive mirror…", flush=True)
        items = fetch_repo(repo)
        coverage_report(repo, items, args.expected)
        path = os.path.join(RAW_DIR, repo.replace("/", "_") + ".jsonl")
        with open(path, "w") as f:
            for it in items:
                f.write(json.dumps(it) + "\n")
        print(f"  wrote {path}", flush=True)

if __name__ == "__main__":
    main()
