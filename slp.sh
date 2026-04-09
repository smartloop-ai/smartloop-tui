#!/usr/bin/env bash
set -euo pipefail

VENV_DIR=".venv"
PYTHON="${VENV_DIR}/bin/python"

if [ ! -f "${PYTHON}" ]; then
    echo "Run 'make install' first." >&2
    exit 1
fi

case "${1:-}" in
    start)
        shift
        exec "$PYTHON" main.py server start "$@"
        ;;
    stop)
        shift
        exec "$PYTHON" main.py server stop "$@"
        ;;
    init)
        shift
        INIT_ARGS=()
        while [[ $# -gt 0 ]]; do
            case "$1" in
                --token|-t)
                    INIT_ARGS+=("--developer-token" "$2"); shift 2 ;;
                --model|-m)
                    INIT_ARGS+=("--model" "$2"); shift 2 ;;
                *)
                    INIT_ARGS+=("$1"); shift ;;
            esac
        done
        exec "$PYTHON" main.py init "${INIT_ARGS[@]}"
        ;;
    resume)
        shift
        SESSION_ID="${1:?Usage: slp.sh resume <session-id>}"
        shift
        exec "$PYTHON" main.py --resume "$SESSION_ID" "$@"
        ;;
    *)
        exec "$PYTHON" main.py "$@"
        ;;
esac
