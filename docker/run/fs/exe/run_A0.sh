#!/bin/bash

. "/ins/setup_venv.sh" "$@"
. "/ins/copy_A0.sh" "$@"

# PMOVES: configurable UI port via environment variable
export WEB_UI_PORT="${WEB_UI_PORT:-80}"

echo "Starting A0 bootstrap manager..."
exec python /exe/self_update_manager.py docker-run-ui
