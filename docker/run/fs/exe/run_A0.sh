#!/bin/bash

. "/ins/setup_venv.sh" "$@"
. "/ins/copy_A0.sh" "$@"

python /a0/prepare.py --dockerized=true
# python /a0/preload.py --dockerized=true # no need to run preload if it's done during container build

# Use WEB_UI_PORT environment variable if set, otherwise default to 80
A0_PORT="${WEB_UI_PORT:-80}"

echo "Starting A0..."
exec python /a0/run_ui.py \
    --dockerized=true \
    --port="$A0_PORT" \
    --host="0.0.0.0"
    # --code_exec_ssh_enabled=true \
    # --code_exec_ssh_addr="localhost" \
    # --code_exec_ssh_port=22 \
    # --code_exec_ssh_user="root" \
    # --code_exec_ssh_pass="toor"
