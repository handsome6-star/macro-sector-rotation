#!/bin/bash
# Double-click to open the dashboard (macOS). Close this Terminal window to stop it.
cd "$(dirname "$0")"
(sleep 4 && open http://localhost:8599) &
./venv/bin/streamlit run app.py --server.port 8599
