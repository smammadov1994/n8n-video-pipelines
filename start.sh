#!/bin/zsh
# Start n8n for the Kaiyros pipeline. Editor: http://localhost:5678
# Data (workflows, executions, login) stays in this folder under .n8n/.
cd "$(dirname "$0")"
mkdir -p output
export PATH="$PWD/node24/node_modules/.bin:$HOME/.local/bin:$PATH"   # local Node 24 for n8n, yt-dlp for downloads
export N8N_USER_FOLDER="$PWD"
export N8N_PORT=5678
export N8N_HOST=localhost
export NODES_EXCLUDE='[]'                                # allow the Execute Command node (off by default in n8n 2)
export N8N_RESTRICT_FILE_ACCESS_TO="$PWD/output"         # the only folder workflows may write to
export N8N_DIAGNOSTICS_ENABLED=false
export N8N_VERSION_NOTIFICATIONS_ENABLED=false
export N8N_PERSONALIZATION_ENABLED=false
exec ./node_modules/.bin/n8n "$@"
