#!/usr/bin/env bash
set -e
PORT=${PORT:-5000}
NODE_KEY_ARG=""
if [ -n "$NODE_KEY" ]; then
  NODE_KEY_ARG="--node-key $NODE_KEY"
fi
exec python main.py --port "$PORT" --host 0.0.0.0 $NODE_KEY_ARG
