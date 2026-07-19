#!/usr/bin/env python3
"""Fetch GitHub issues (PRs filtered out) into data/raw/<owner>_<repo>.jsonl."""
import argparse, json, os, sys, time
import requests

RAW_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "raw")

def fetch_repo(repo: str, cap: int, token: str | None) -> list[dict]:
    headers = {"Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    out, page = [], 1
    while len(out) < cap:
        r = requests.get(
            f"https://api.github.com/repos/{repo}/issues",
            params={"state": "all", "per_page": 100, "page": page},
            headers=headers, timeout=30,
        )
        if r.status_code in (403, 429):
            sys.exit(f"Rate limited on {repo}. Set GITHUB_TOKEN (5,000 req/hr) or wait. "
                     f"Kept {len(out)} issues fetched so far in memory only.")
        r.raise_for_status()
        data = r.json()
        if not data:
            break
        for it in data:
            if "pull_request" in it:
                continue
            out.append({
                "id": f"{repo}#{it['number']}",
                "source": repo,
                "state": it["state"],
                "title": it.get("title") or "",
                "body": (it.get("body") or "")[:1200],
                "url": it["html_url"],
                "created_at": it.get("created_at"),
            })
        print(f"  {repo}: page {page}, {len(out)} issues so far", flush=True)
        if len(data) < 100:
            break
        page += 1
        time.sleep(0.5)
    return out[:cap]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", action="append", required=True, help="owner/name (repeatable)")
    ap.add_argument("--max", type=int, default=1000, help="max issues per repo")
    args = ap.parse_args()
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        print("WARNING: no GITHUB_TOKEN set — anonymous limit is ~60 requests/hr.", flush=True)
    os.makedirs(RAW_DIR, exist_ok=True)
    for repo in args.repo:
        print(f"Fetching {repo} (cap {args.max})…", flush=True)
        items = fetch_repo(repo, args.max, token)
        path = os.path.join(RAW_DIR, repo.replace("/", "_") + ".jsonl")
        with open(path, "w") as f:
            for it in items:
                f.write(json.dumps(it) + "\n")
        print(f"Wrote {len(items)} issues → {path}", flush=True)

if __name__ == "__main__":
    main()
