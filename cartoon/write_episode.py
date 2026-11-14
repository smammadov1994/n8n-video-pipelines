"""Write one episode's script.json for a show, from one sentence saying what the episode is about.

    python3 write_episode.py <show>/<episode> "Pip counts five apples into a basket" [--scenes 5] [--redo]

The script is written by a model that is given the show (character, place, rules) and the way scenes have to be
written for the video model to get them right. Prints ONE JSON line and always exits 0. Read the script before
filming: it is cheaper to fix a sentence than to refilm a scene.
"""
import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import show as S  # noqa: E402

WRITER = """You write one short episode of a cartoon for an automatic pipeline. For every scene an image model draws a
START PICTURE, a voice speaks the line, and a video model animates the start picture for the length of the line.

The show
- Kind of cartoon: {what}
- Character, named {name}: {character}
- Place (every scene happens here, seen from the same camera position): {place}
- Who watches: {audience}

The episode: {idea}
Number of scenes: {scenes}

How scenes must be written. Each of these came from a scene that went wrong.
1. One scene is one camera position and ONE small action, a few seconds long. Split anything bigger into two scenes.
2. "says" is what {name} says aloud: one or two short sentences, at most 16 words, plain words, no numbers written as
   digits, no abbreviations. Repeated sound words work well with a repeated action ("Stir, stir, stir.").
3. "picture" describes the START of the scene as a still picture, in full, every scene again from nothing: where
   {name} is and how much of {name} is seen, then every object in the scene with its position ("left to right: ...")
   and its state at that moment, then what {name} is holding or pointing at. Never write "as before".
4. Everything the scene uses is ALREADY VISIBLE in its picture. Nothing may be fetched, opened or brought in from
   outside the frame. If something is added to something else, the picture shows it already held or lifted.
5. The state of every object carries over: what was done in scene 3 is how things look at the start of scene 4.
   Objects that are finished with stay where they were unless a scene moved them.
6. "does" describes the movement as things that are SEEN happening, step by step, tied to the words ("... on
   'plate'"). When something moves from one place to another, say it is seen travelling the whole way. Add:
   "Nothing appears from nowhere and nothing disappears." where objects are handled.
7. Every "does" ends with: "The mouth opens and closes with every word. After the last word {name} closes the mouth
   and smiles." (use the right word if this character has no mouth).
8. Name objects the same way every time, with their colour and material ("the small round wooden board").
   No labels, no writing on anything.
9. Scene 1 greets and says what the episode is about. The last scene shows the result, and says goodbye.
10. Obey the show's own rules: {picture_rules} {clip_rules}
{safety}

Answer with ONLY a JSON array of {scenes} objects, no markdown fence, each exactly:
{{"n": 1, "says": "...", "picture": "...", "does": "..."}}"""

SAFETY = ("11. Children copy what they see. Nothing sharp, hot or dangerous is used; anything of that kind is "
          "\"a job for a grown-up\" and is not shown being done.")


def say(**out):
    print(json.dumps(out, ensure_ascii=False))


def main():
    a = argparse.ArgumentParser()
    a.add_argument("episode"); a.add_argument("idea"); a.add_argument("--scenes", type=int, default=5)
    a.add_argument("--redo", action="store_true")
    o = a.parse_args()
    ep = S.episode_dir(o.episode)
    show = S.load_show(ep.parent)
    out = ep / "script.json"
    if out.exists() and not o.redo:
        return say(ok=False, error=f"{o.episode} already has a script.json. Add --redo to write it again.")
    scenes = max(2, min(o.scenes, 10))
    audience = show.get("audience") or "small children"
    reply = S.ask_claude(WRITER.format(what=show["what"], name=show["name"], character=show["character"], place=show["place"],
                                       audience=audience, idea=o.idea, scenes=scenes, picture_rules=show["picture_rules"],
                                       clip_rules=show["clip_rules"], safety=SAFETY if "child" in audience.lower() else ""),
                         show["folder"], "opus")
    if isinstance(reply, dict):
        reply = reply.get("scenes") or []
    script = [{"n": i, "says": str(s["says"]).strip(), "picture": str(s["picture"]).strip(), "does": str(s["does"]).strip()}
              for i, s in enumerate(reply, 1)]
    if len(script) < 2:
        return say(ok=False, error="the writer returned no usable scenes")
    ep.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(script, indent=1, ensure_ascii=False) + "\n")
    say(ok=True, episode=o.episode, file=str(out), scenes=len(script), lines=[s["says"] for s in script])


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        say(ok=False, error=f"{type(e).__name__}: {e}"[:400])
