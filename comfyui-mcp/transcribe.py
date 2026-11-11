# /// script
# requires-python = ">=3.10"
# dependencies = ["mlx-whisper>=0.4", "av>=12", "numpy"]
# ///
"""Transcribe a video/audio file with Whisper on Apple Silicon.

    uv run transcribe.py input.mp4 output.json [language]

Decodes audio with PyAV (no ffmpeg needed), runs mlx-community/whisper-large-v3-turbo,
writes {"text", "language", "segments": [{"start", "end", "text"}]}.
"""
import json
import sys

import av
import mlx_whisper
import numpy as np

MODEL = "mlx-community/whisper-large-v3-turbo"


def load_audio(path: str) -> np.ndarray:
    chunks = []
    with av.open(path) as f:
        if not f.streams.audio:
            raise SystemExit("No audio track in this file.")
        res = av.AudioResampler(format="flt", layout="mono", rate=16000)
        for frame in f.decode(audio=0):
            for r in res.resample(frame):
                chunks.append(r.to_ndarray().reshape(-1))
        for r in res.resample(None):
            chunks.append(r.to_ndarray().reshape(-1))
    return np.concatenate(chunks).astype(np.float32) if chunks else np.zeros(0, np.float32)


def main() -> None:
    src, dest = sys.argv[1], sys.argv[2]
    lang = sys.argv[3] if len(sys.argv) > 3 else None
    audio = load_audio(src)
    r = mlx_whisper.transcribe(audio, path_or_hf_repo=MODEL, language=lang)
    out = {
        "text": r["text"].strip(),
        "language": r.get("language"),
        "seconds": round(len(audio) / 16000, 2),
        "segments": [{"start": round(s["start"], 2), "end": round(s["end"], 2), "text": s["text"].strip()}
                     for s in r["segments"]],
    }
    with open(dest, "w") as f:
        json.dump(out, f, indent=2)
    print("ok", dest)


if __name__ == "__main__":
    main()
