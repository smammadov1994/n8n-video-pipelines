# Runbook (how to rebuild and run everything)

Short copy of how to rebuild and run everything.
Rules the machine follows: `RULEBOOK.md`.

## The two machines (Vast.ai, ComfyUI template, RTX 5090)
- **Episode machine** (100 GB disk): install with `setup_5090.sh`. Connect the Mac: copy the ComfyUI IP link in its Instance Portal, run `python3 set_5090.py`.
- **Swap machine** (200 GB disk): install with `swap/box/install.sh`, copy `swap/box/run_swap.py` + `swap/box/queue.sh` to `/workspace`, put `swap/character.png` in `ComfyUI/input`, start `nohup /workspace/queue.sh &`. Connect the Mac: copy its ComfyUI IP link, run `python3 set_5090.py --swap`.

## n8n (http://localhost:5678)
- Start: `nohup caffeinate -i -s zsh -c 'while true; do ./start.sh start; sleep 20; done' >> n8n.log 2>&1 &`
- **Episode machine** workflow (`workflows/episode-machine.json`): topic -> script -> pictures -> shoot -> checks -> publish to YouTube (Short + full video, one episode per 3 hours).
- **Swap machine** workflow (`workflows/swap-machine.json`): pick Kaiyros clips -> her voice -> send to swap machine -> collect into `swap/finished/`. TikTok posting step waits for the TikTok sign-in.
- After changing a workflow file: `./start.sh import:workflow --input=workflows/<file>` then `./start.sh publish:workflow --id=<id>` and restart n8n (between episodes).

## Daily
- Health: `./status.sh`. Pause episodes: create `episodes/PAUSE`. Finished episodes: `episodes/index.html`.
- YouTube poster: `poster/yt.py` (sign in once with `yt.py login`).
