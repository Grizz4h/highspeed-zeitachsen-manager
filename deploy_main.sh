#!/usr/bin/env bash
set -euo pipefail

cd /opt/highspeed/toolbox

git fetch origin main
git reset --hard origin/main

/opt/highspeed/toolbox/.venv/bin/pip install -U streamlit pillow numpy pandas matplotlib requests

sudo systemctl restart highspeed-toolbox
