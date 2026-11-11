#!/bin/bash
# Runs ON the swap machine (/workspace/queue.sh). Swaps every input/q_<id>.mp4 that has no result yet, one at a time, forever.
cd /workspace/ComfyUI
while true; do
  for f in input/q_*.mp4; do
    [ -f "$f" ] || continue
    id=$(basename "$f" .mp4); id=${id#q_}
    [ -f /workspace/results/$id.mp4 ] || [ -f /workspace/results/$id.failed ] && continue
    before=$(ls output/h3_oneclick_swap/*.mp4 2>/dev/null | wc -l)
    python3 /workspace/run_swap.py $(basename "$f") > /workspace/results/$id.log 2>&1
    after=$(ls output/h3_oneclick_swap/*.mp4 2>/dev/null | wc -l)
    if [ "$after" -gt "$before" ]; then cp "$(ls -t output/h3_oneclick_swap/*.mp4 | head -1)" /workspace/results/$id.mp4; echo "$(date +%H:%M) done $id" >> /workspace/queue.log
    else touch /workspace/results/$id.failed; echo "$(date +%H:%M) FAILED $id" >> /workspace/queue.log; fi
  done
  sleep 60
done
