#!/usr/bin/env python3
"""Run the big-mistake picture check over the takes of finished episodes (they may predate the check).

    audit_looks.py <episode folder> [...]          # report only
    audit_looks.py --requeue <episode folder> ...  # also set flagged takes aside so the machine reshoots them

A requeued episode loses its "finished" mark; the n8n Episode machine picks it up again and reshoots only
the takes that were set aside (into <folder>/set_aside/).
"""
import json
import shutil
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from clip_check import look_at  # noqa: E402

requeue = "--requeue" in sys.argv
folders = [Path(a).resolve() for a in sys.argv[1:] if not a.startswith("--")]
jobs = []
for folder in folders:
    for record in sorted((folder / "fish").glob("take*_????????.json")):
        take = json.loads(record.read_text())
        jobs.append((folder, record, take))
with ThreadPoolExecutor(6) as pool:
    looks = list(pool.map(lambda j: look_at(j[2]["file"], j[2].get("speech_end")), jobs))
bad_folders = set()
for (folder, record, take), look in zip(jobs, looks):
    if look["good"]:
        continue
    print(f"{folder.name} take {take['n']} ({take['set']}): {', '.join(look['problems'])} - {look['note']}")
    if requeue and "check_did_not_run" not in look["problems"]:
        aside = folder / "set_aside"
        aside.mkdir(exist_ok=True)
        for f in (folder / "fish").glob(record.stem + "*"):
            shutil.move(str(f), aside / f.name)
        bad_folders.add(folder)
for folder in bad_folders:
    rf = folder / "result.json"
    r = json.loads(rf.read_text())
    r.pop("fish", None)
    rf.write_text(json.dumps(r, indent=2))
print(json.dumps({"takes_checked": len(jobs), "flagged": sum(not l["good"] for l in looks), "requeued": sorted(f.name for f in bad_folders)}))
