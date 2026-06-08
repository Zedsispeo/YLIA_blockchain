#!/usr/bin/env bash
# Lance deux nœuds YLIA (ports 5000 et 5001) pour une démo manuelle.
# Arrêt : Ctrl-C (les deux nœuds sont tués).
set -euo pipefail
cd "$(dirname "$0")/.."

echo "Nœud A → http://127.0.0.1:5000   (index API : curl http://127.0.0.1:5000/)"
echo "Nœud B → http://127.0.0.1:5001   (index API : curl http://127.0.0.1:5001/)"
echo "Ctrl-C pour tout arrêter."

python main.py --port 5000 &
PID_A=$!
python main.py --port 5001 &
PID_B=$!

trap 'kill $PID_A $PID_B 2>/dev/null || true' EXIT INT TERM
wait
