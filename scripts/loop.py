#!/usr/bin/env python3
"""Continuous autonomous issue-fixing loop. Never stops."""
import subprocess, sys, os, time, json

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DISCOVER = os.path.join(SKILL_DIR, "scripts", "discover.py")
SEEN = os.path.join(SKILL_DIR, "seen_issues.json")

def run(cmd, timeout=300):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, shell=True)
        return r.stdout.strip(), r.stderr.strip(), r.returncode
    except:
        return "", "", 1

def discover_round():
    """Run discovery. Returns list of candidates."""
    stdout, stderr, rc = run(f"{sys.executable} {DISCOVER} --direct --keyword --kw-min-stars 5 --max-days 90 --max-candidates 5", timeout=300)
    if rc != 0:
        return []
    try:
        data = json.loads(stdout)
        return data.get("candidates", [])
    except:
        return []

def seen_count():
    if not os.path.exists(SEEN):
        return 0
    with open(SEEN) as f:
        return len(json.load(f))

dry = 0
round_num = 0
while True:
    round_num += 1
    sc = seen_count()
    print(f"\n{'='*40} ROUND {round_num} (seen: {sc}) dry: {dry} {'='*40}", flush=True)

    candidates = discover_round()
    if not candidates:
        dry += 1
        print(f"  No candidates. dry={dry}/3", flush=True)
        if dry >= 3:
            print("  Expanding: lowering kw-min-stars to 3, max-days to 120", flush=True)
            # Modify search params in-place for next run via env
            os.environ["IFX_MIN_STARS"] = "3"
            os.environ["IFX_MAX_DAYS"] = "120"
        time.sleep(30)
        continue

    dry = 0
    for c in candidates:
        print(f"  {c['repo']}#{c['issue_number']} — {c['issue_title'][:100]}", flush=True)

    print(f"  Found {len(candidates)} — fix manually or re-run", flush=True)
    time.sleep(30)

if __name__ == "__main__":
    main()
