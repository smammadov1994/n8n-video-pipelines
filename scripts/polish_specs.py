#!/usr/bin/env python3
"""Re-read already planned scripts for lines that are hard to follow by ear, and fix them (lines + her direction).
    polish_specs.py <episode folder> [...]"""
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import plan_episode as pe
for a in sys.argv[1:]:
    folder = Path(a).resolve(); f = folder / "spec.json"; spec = json.loads(f.read_text())
    if not spec["takes"][-1]["says"].rstrip().endswith("Follow for more."):
        pass                                             # the polish prompt restores it
    changes = pe.polish(folder, spec.get("topic", spec["title"]), spec)
    if changes:
        pe.redirect(folder, spec, {c["n"] for c in changes})
        spec.setdefault("fact_check", {}).setdefault("fixes", []).extend(changes)
        f.write_text(json.dumps(spec, indent=2) + "\n")
    print(folder.name, len(changes), "lines reworded")
    for c in changes: print("   ", c["n"], "WAS:", c["was"], "\n      NOW:", c["now"])
