"""On the GPU box: remove queued (not yet running) clips by name.   python3 drop.py pixel_2 [other_name ...]"""
import json, sys, urllib.request
q = json.load(urllib.request.urlopen("http://localhost:18188/queue"))
ids = [item[1] for item in q["queue_pending"] if any(n.get("class_type") == "SaveVideo" and n["inputs"]["filename_prefix"].split("/")[-1] in sys.argv[1:] for n in item[2].values())]
urllib.request.urlopen(urllib.request.Request("http://localhost:18188/queue", json.dumps({"delete": ids}).encode(), {"Content-Type": "application/json"}))
print("dropped", len(ids))
