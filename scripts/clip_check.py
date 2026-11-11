#!/usr/bin/env python3
"""Look at a finished talking clip for the mistakes video models make part-way through.

    python3 clip_check.py <clip.mp4> [seconds of speech]     # prints the verdict as JSON

Six frames (the first one plus five spread over the clip) go on one sheet; Claude answers factual
questions about them: facts, not opinions, and only big mistakes a viewer would notice.
A clip is good only when every answer is false. A check that fails to run counts as not good.
"""
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from understand import ask_claude  # noqa: E402

# Only the big things (the owner, 2026-11-10): what a viewer notices at normal speed without pausing. Small stuff
# is fine and is NOT asked about: a watch or bracelet, a slightly different necklace, small background shifts
# from camera movement, an accessory that is there in one shot and gone in the next.
QUESTIONS = {
    "limb_mistake": "an extra arm or hand, a missing arm, an arm that swaps sides or bends the wrong way, or a hand that is obviously mangled (clearly six or more fingers, or fingers melted into a lump). Ordinary motion blur, fingers held together, and one hand resting on, over or against the other do not count",
    "hands_too_big": "in any frame a hand that is clearly oversized for her body (about as big as her face or bigger), or thick and heavy like a large man's hand rather than her own slender hand",
    "body_through_object": "a part of her body clearly sunk into or passing through a solid object or surface (for example her torso inside a table)",
    "different_person": "her face in a later frame is obviously a different woman from frame 1, or is badly warped. Normal talking mouth shapes, blinks, smiles and raised eyebrows do not count",
    "outfit_swapped": "her top is a clearly different garment or colour than in frame 1",
    "place_swapped": "a later frame is clearly in a different place than frame 1, or a large object pops into or out of the scene. Small changes from the camera moving or her shifting do not count",
    "turned_away": "her back is to the camera, or her face is turned away from the lens in most frames",
    "text_or_extra_person": "readable text, a caption, a logo or watermark on screen, or a second person",
}

ASK = """Read the image file {name} in the current folder. It is a sheet of six frames from one AI-generated video clip of a woman talking to the camera, in time order left to right, top row first. Frame 1 (top left) is the very first frame of the clip.

We only care about big, obvious mistakes: things an ordinary viewer would notice at normal playback speed without pausing or zooming. Ignore small details such as jewellery, watches, bracelets, tiny differences in the necklace or mic, and slight background shifts.

Answer each question as a plain fact. Answer true only when the thing is clearly visible and obvious; when in doubt answer false.
{questions}

Answer with ONLY one JSON object: {{{keys}, "note": "one short sentence naming what you saw and in which frame, or 'nothing wrong'"}}"""


def sheet_of(clip, seconds=None):
    """Six frames on one picture, saved next to the clip."""
    clip = Path(clip)
    if not seconds:
        seconds = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(clip)],
                                       capture_output=True, text=True).stdout.strip() or 5)
    times = [0.05] + [round(seconds * k / 5.2, 2) for k in range(1, 6)]
    args, n = [], len(times)
    for t in times:
        args += ["-ss", str(t), "-i", str(clip)]
    fc = "".join(f"[{i}:v]trim=end_frame=1,scale=672:-2[f{i}];" for i in range(n)) + \
        "".join(f"[f{i}]" for i in range(3)) + "hstack=3[a];" + "".join(f"[f{i}]" for i in range(3, 6)) + "hstack=3[b];[a][b]vstack[v]"
    sheet = clip.with_suffix(".look.jpg")
    r = subprocess.run(["ffmpeg", "-v", "error", "-y", *args, "-filter_complex", fc, "-map", "[v]", "-frames:v", "1", "-q:v", "3", str(sheet)],
                       capture_output=True, text=True)
    if r.returncode:
        raise RuntimeError(f"frame sheet failed: {r.stderr.strip()[-200:]}")
    return sheet


def look_at(clip, seconds=None):
    """{"good": bool, "problems": [...], "note": "..."}; cached next to the clip."""
    clip = Path(clip)
    saved = clip.with_suffix(".look.json")
    if saved.exists():
        return json.loads(saved.read_text())
    try:
        sheet = sheet_of(clip, seconds)
        v = ask_claude(ASK.format(name=sheet.name, questions="\n".join(f"- {k}: {q}" for k, q in QUESTIONS.items()),
                                  keys=", ".join(f'"{k}": true or false' for k in QUESTIONS)), sheet.parent, "sonnet")
        bad = [k for k in QUESTIONS if v.get(k) is not False]
        out = {"good": not bad, "problems": bad, "note": str(v.get("note") or "")}
    except Exception as e:
        return {"good": False, "problems": ["check_did_not_run"], "note": str(e)[:200]}     # not cached: try again next time
    saved.write_text(json.dumps(out, indent=2))
    return out


if __name__ == "__main__":
    print(json.dumps(look_at(sys.argv[1], float(sys.argv[2]) if len(sys.argv) > 2 else None)))
