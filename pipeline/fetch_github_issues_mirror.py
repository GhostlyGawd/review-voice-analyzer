#!/usr/bin/env python3
"""Fetch GitHub issues from public mirrors (no GitHub credentials involved).

For environments where api.github.com is scoped/blocked (e.g. Claude Code
remote sessions). Two complementary layers:

1. BULK BODIES — GH Archive `git.github_events` on ClickHouse Cloud's public
   demo instance (sql-clickhouse.clickhouse.com, anonymous `demo` user):
   title + body + state per issue. Continuous coverage from repo creation,
   but recent months (~last 3-4) are under-ingested upstream.
2. CENSUS TOP-UP — issues.ecosyste.ms open research API: complete recent
   census (number, title, labels, state, dates; PR-flagged) but NO bodies.
   Issues missing from layer 1 are emitted as clearly-marked title-only
   records so classifiers can weigh them conservatively.

The per-repo coverage report prints what each layer contributed and the
residual gap vs --expected. Partial coverage must be a conscious,
documented decision (methodology rule 1) — prefer fetch_github_issues.py
with a GITHUB_TOKEN wherever the real API is reachable.
"""
import argparse, json, os, sys, time
import requests

RAW_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "raw")
CH_ENDPOINT = "https://sql-clickhouse.clickhouse.com/?user=demo"
ECO_BASE = "https://issues.ecosyste.ms/api/v1/hosts/GitHub/repositories"
BODY_CAP = 1200
RANGE = 3000  # issue numbers per ClickHouse query chunk

def http(method, url, tries=4, **kw):
    for attempt in range(tries):
        try:
            r = requests.request(method, url, timeout=120, **kw)
        except requests.RequestException:
            time.sleep(2 ** (attempt + 1))
            continue
        if r.status_code in (429, 502, 503):
            time.sleep(2 ** (attempt + 1))
            continue
        r.raise_for_status()
        return r
    sys.exit(f"{url.split('/')[2]} unavailable after {tries} tries.")

def ch(sql):
    return http("POST", CH_ENDPOINT, data=sql.encode()).text

def fetch_bodies(repo):
    """Layer 1: issues with bodies from git.github_events."""
    max_num = int(ch(
        f"SELECT max(number) FROM git.github_events WHERE repo_name='{repo}' "
        "AND event_type='IssuesEvent' FORMAT TSV").strip() or 0)
    items = {}
    for lo in range(1, max_num + 1, RANGE):
        rows = ch(
            "SELECT number, argMax(title, created_at) AS title, "
            f"argMax(substring(body, 1, {BODY_CAP}), created_at) AS body, "
            "argMax(state, created_at) AS state, min(created_at) AS created "
            f"FROM git.github_events WHERE repo_name='{repo}' "
            "AND event_type='IssuesEvent' "
            f"AND number BETWEEN {lo} AND {lo + RANGE - 1} "
            "GROUP BY number ORDER BY number FORMAT JSONEachRow")
        for line in rows.splitlines():
            row = json.loads(line)
            state = row["state"] if row["state"] in ("open", "closed") else "open"
            items[row["number"]] = {
                "id": f"{repo}#{row['number']}",
                "source": repo,
                "state": state,
                "title": row["title"] or "",
                "body": (row["body"] or "")[:BODY_CAP],
                "url": f"https://github.com/{repo}/issues/{row['number']}",
                "created_at": row["created"].replace(" ", "T") + "Z",
            }
        time.sleep(0.4)
    return items

def fetch_census(repo):
    """Layer 2: complete recent census (no bodies) from ecosyste.ms."""
    census, page = {}, 1
    while True:
        r = http("GET", f"{ECO_BASE}/{repo.replace('/', '%2F')}/issues",
                 params={"per_page": 100, "page": page},
                 headers={"User-Agent": "review-voice-analyzer research"})
        batch = r.json()
        if not batch:
            break
        for it in batch:
            if it.get("pull_request"):
                continue
            census[it["number"]] = it
        if 'rel="next"' not in (r.headers.get("link") or ""):
            break
        page += 1
        time.sleep(0.3)
    return census

def census_item(repo, it):
    labels = ", ".join(l if isinstance(l, str) else l.get("name", "")
                       for l in (it.get("labels") or []))
    body = "[census record: issue body unavailable from public mirrors]"
    if labels:
        body += f" (labels: {labels})"
    return {
        "id": f"{repo}#{it['number']}",
        "source": repo,
        "state": it.get("state") or "open",
        "title": it.get("title") or "",
        "body": body,
        "url": it.get("html_url") or f"https://github.com/{repo}/issues/{it['number']}",
        "created_at": it.get("created_at") or "",
    }

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", action="append", required=True, help="owner/name (repeatable)")
    ap.add_argument("--expected", type=int, default=0,
                    help="known real issue count, for the coverage report")
    args = ap.parse_args()
    os.makedirs(RAW_DIR, exist_ok=True)
    for repo in args.repo:
        print(f"Fetching {repo} from public mirrors…", flush=True)
        bodies = fetch_bodies(repo)
        print(f"  layer 1 (GH Archive mirror): {len(bodies)} issues with bodies", flush=True)
        census = fetch_census(repo)
        topup = [census_item(repo, it) for n, it in sorted(census.items())
                 if n not in bodies]
        print(f"  layer 2 (ecosyste.ms census): {len(census)} issues seen, "
              f"{len(topup)} added as title-only records", flush=True)
        items = sorted(list(bodies.values()) + topup, key=lambda i: i["id"])
        total = len(items)
        if args.expected:
            pct = 100 * total / args.expected
            print(f"  UNION: {total} issues vs expected ~{args.expected} "
                  f"({pct:.0f}%). Residual gap = issues with no event in "
                  f"either mirror window; document before tallying.", flush=True)
        path = os.path.join(RAW_DIR, repo.replace("/", "_") + ".jsonl")
        with open(path, "w") as f:
            for it in items:
                f.write(json.dumps(it) + "\n")
        print(f"  wrote {total} → {path}", flush=True)

if __name__ == "__main__":
    main()
