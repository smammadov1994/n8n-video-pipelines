# ComfyUI MCP server (HyperFlow H3 Flash)

Lets Claude (Desktop or Code) and Codex make videos on your Vast.ai ComfyUI just by asking:
*"Make a 10-second surreal analog clip of a jellyfish made of TV static, 8 steps."*
The finished MP4 is downloaded to `~/Movies/comfyui-mcp/`.

## Tools it gives Claude / Codex

| Tool | What it does |
|---|---|
| `generate_video` | Prompt, seconds (5–15), steps (4/6/8), seed, size, optional start/end image paths. Waits up to 4 min, then returns a job ID to keep polling. |
| `get_video_status` | Waits for or checks a job, and downloads the MP4 when it's done. |
| `list_queue` / `cancel` | See what's running or queued, and cancel one job or all of them. |
| `list_recent_videos` / `download_video` | Browse past jobs and download their outputs. |
| `free_gpu_memory` | Unload models on the server. |
| `server_info` | Connection test: shows the GPU, free VRAM, and which workflows were found. |

## 1. Install uv (one time)

```bash
brew install uv
```

`uv` runs `server.py` and installs its two dependencies (`mcp` and `httpx`) automatically.

## 2. Export your workflows from ComfyUI (one time)

The server queues the exact workflows you built, so it needs them in ComfyUI's **API format**.

1. In ComfyUI, open **hyperflow_t2v**. Make sure the HyperFlow GGUF Loader shows `fl2va_gguf/...Q4_K_M.gguf` and that there are no red nodes.
2. Choose **Workflow → Export (API)**. Save the file as **`t2v.json`** in this folder's `workflows/` directory.
3. Optional: do the same for **hyperflow_i2v**, saved as **`i2v.json`** (start from an image), and **hyperflow_flf2v**, saved as **`flf2v.json`** (start and end images).

The folder should look like this:
```
comfyui-mcp/
  server.py
  workflows/
    t2v.json
    i2v.json     (optional)
    flf2v.json   (optional)
```

The server only changes the prompt, width, height, length, seed, steps and input images. Everything else runs exactly as saved. If you tweak the workflow in ComfyUI, re-export it.

## 3. Connect it

You need two values:
- **COMFY_URL** is the ComfyUI tunnel from Instance Portal → Tunnels, the `localhost:8188` row, e.g. `https://YOUR-TUNNEL.trycloudflare.com`. Leave off `?token=`.
- **COMFY_TOKEN** is your token (`echo $OPEN_BUTTON_TOKEN` in the Jupyter terminal).

Replace `/Users/YOU/comfyui-mcp` below with wherever you put this folder.

### Claude Code
```bash
claude mcp add comfyui --scope user \
  -e COMFY_URL=https://YOUR-TUNNEL.trycloudflare.com \
  -e COMFY_TOKEN=YOUR_TOKEN \
  -- uv run /Users/YOU/comfyui-mcp/server.py
```
Check it with `claude mcp list`. In a session, run `/mcp` to see its tools.

### Claude Desktop
Go to **Settings → Developer → Edit Config**, which opens `claude_desktop_config.json`, and add:
```json
{
  "mcpServers": {
    "comfyui": {
      "command": "uv",
      "args": ["run", "/Users/YOU/comfyui-mcp/server.py"],
      "env": {
        "COMFY_URL": "https://YOUR-TUNNEL.trycloudflare.com",
        "COMFY_TOKEN": "YOUR_TOKEN"
      }
    }
  }
}
```
Fully quit and reopen Claude Desktop. If it says `uv` isn't found, use the full path from `which uv` (e.g. `/opt/homebrew/bin/uv`).

### Codex
Add to `~/.codex/config.toml`:
```toml
[mcp_servers.comfyui]
command = "uv"
args = ["run", "/Users/YOU/comfyui-mcp/server.py"]
env = { COMFY_URL = "https://YOUR-TUNNEL.trycloudflare.com", COMFY_TOKEN = "YOUR_TOKEN" }
tool_timeout_sec = 300
startup_timeout_sec = 60
```
`tool_timeout_sec` matters here: a 5-second clip takes about 2 minutes, which is longer than Codex's default tool timeout.

## 4. Try it

Ask: **"Run server_info on comfyui."** You should see the RTX 5090 and `workflows_found: ["t2v", ...]`. Then:

> Make a 5-second video: grainy 16mm film, a jellyfish made of TV static drifting over a salt flat at dusk, slow dolly forward, tape hum and distant piano.

For long clips (about 10 minutes for 15 s), the tool returns a `prompt_id` after 4 minutes. Ask Claude to "keep waiting on that video" and it calls `get_video_status`.

## Troubleshooting

| Problem | Fix |
|---|---|
| "refused the request (401)" or "HTML page instead of JSON" | Wrong token, or COMFY_URL isn't the 8188 tunnel. |
| Connection errors after restarting the instance | The trycloudflare URL changed. Copy the new 8188 tunnel URL into your config and restart Claude or Codex. |
| "workflow not found" / "UI-format workflow" | Re-export with **Export (API)**, not plain Export or Save, and name it `t2v.json`. |
| "ComfyUI rejected the workflow" | A model name in the exported workflow doesn't exist on the server. Open the workflow in ComfyUI, fix the red node, and re-export. |
| Tool times out in Claude Code | Start Claude Code with `MCP_TOOL_TIMEOUT=600000 claude`, or use a smaller `wait_seconds` and poll with `get_video_status`. |

## Security

Your token unlocks the whole instance, including the terminal, not just ComfyUI. It lives only in your local MCP config. Don't commit that config anywhere. To change the token, destroy the instance and rent a new one.
