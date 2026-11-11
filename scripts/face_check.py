# /// script
# requires-python = ">=3.10,<3.13"
# dependencies = ["insightface==0.7.3", "onnxruntime>=1.17", "opencv-python-headless>=4.9", "numpy<2"]
# ///
"""Is the woman in these clips the same woman as in the master picture?

    uv run face_check.py <master picture> <clip or picture> [more ...]

For each clip: 8 frames spread through it, the biggest face in each frame, and how closely that
face matches the master (0 = stranger, 1 = identical). Face matching looks at bone structure, so
lighting, angle and expression move the score only a little.

Prints one JSON line per file: {"file", "frames", "median", "lowest", "face_height"}.
  median      the typical match across the clip
  lowest      the worst frame (a face that drifts partway through shows up here)
  face_height her face as a share of the frame height, in the first frame (small = model has to guess)
"""
import json
import sys

import cv2
import numpy as np
from insightface.app import FaceAnalysis

FRAMES = 8
_app = None


def app():
    global _app
    if _app is None:
        _app = FaceAnalysis(name="buffalo_l", allowed_modules=["detection", "recognition"],
                            providers=["CPUExecutionProvider"])
        _app.prepare(ctx_id=-1, det_size=(640, 640))
    return _app


def biggest_face(img):
    faces = app().get(img)
    if not faces:
        return None
    return max(faces, key=lambda f: (f.bbox[2] - f.bbox[0]) * (f.bbox[3] - f.bbox[1]))


def frames_of(path):
    if path.lower().endswith((".png", ".jpg", ".jpeg", ".webp")):
        img = cv2.imread(path)
        return [img] if img is not None else []
    cap = cv2.VideoCapture(path)
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    out = []
    for i in np.linspace(2, max(total - 3, 2), FRAMES).astype(int):
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(i))
        ok, img = cap.read()
        if ok:
            out.append(img)
    cap.release()
    return out


def check(master_vec, path):
    scores, first_height, xs = [], None, []
    for img in frames_of(path):
        f = biggest_face(img)
        if f is None:
            continue
        if first_height is None:
            first_height = round(float(f.bbox[3] - f.bbox[1]) / img.shape[0], 3)
        xs.append(float(f.bbox[0] + f.bbox[2]) / 2 / img.shape[1])
        scores.append(float(np.dot(master_vec, f.normed_embedding)))
    if not scores:
        return {"file": path, "frames": 0, "median": None, "lowest": None, "face_height": None, "face_x": None}
    return {"file": path, "frames": len(scores), "median": round(float(np.median(scores)), 3),
            "lowest": round(min(scores), 3), "face_height": first_height,
            "face_x": round(float(np.median(xs)), 3)}   # where her face sits left-to-right, 0-1 (for vertical crops)


def main():
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    master = biggest_face(cv2.imread(sys.argv[1]))
    if master is None:
        sys.exit("No face found in the master picture.")
    for path in sys.argv[2:]:
        print(json.dumps(check(master.normed_embedding, path)), flush=True)


if __name__ == "__main__":
    main()
