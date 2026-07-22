
#!/usr/bin/env bash

set -euo pipefail



cd /proj/zefflab/projects/Flooding/pipeline/web_launcher

source /proj/zefflab/projects/Flooding/pipeline/envs/web_launcher/bin/activate



PORT="${WEB_LAUNCHER_PORT:-5000}"



echo

echo "Starting SFINCS Web Launcher"

echo "Open this in Firefox inside the same Open OnDemand Desktop session:"

echo "  http://127.0.0.1:${PORT}"

echo

echo "Press Ctrl+C in this terminal to stop the launcher."

echo



WEB_LAUNCHER_PORT="$PORT" python app.py

