#!/usr/bin/env bash
set -euo pipefail
# Usage: ./scripts/init_network.sh
# Requires: curl, jq (or python3 as fallback)
#
# Initialises a 3-node YLIA network:
#   1. Waits for all nodes to be healthy.
#   2. Wires up peers so every node knows the other two.
#   3. Registers node_b, node_c, and the demo 'responsable' as on-chain authorities.
#   4. Mines a block on node_a to make those registrations effective.
#   5. Resolves conflicts on node_b and node_c so they sync the new block.

HOST=${HOST:-localhost}
NODE_A_PORT=${A_PORT:-5000}
NODE_B_PORT=${B_PORT:-5001}
NODE_C_PORT=${C_PORT:-5002}
TIMEOUT=${TIMEOUT:-30}

# ── JSON helpers: use jq if available, fall back to python3 ──────────────────
if command -v jq >/dev/null 2>&1; then
  json_pp()  { jq -C .; }
  json_get() { jq -r "$1"; }
else
  json_pp()  { python3 -m json.tool; }
  json_get() {
    local expr=$1
    python3 -c "
import json, sys
d = json.load(sys.stdin)
for k in '${expr}'.lstrip('.').split('.'):
    d = d[k]
print(d)
"
  }
fi

wait_up() {
  local url=$1
  local deadline=$((SECONDS + TIMEOUT))
  while [ $SECONDS -lt $deadline ]; do
    if curl -s --connect-timeout 1 "$url/health" >/dev/null 2>&1; then
      return 0
    fi
    sleep 0.5
  done
  return 1
}

echo "==> Waiting for nodes to be ready..."
wait_up "http://$HOST:$NODE_A_PORT" || { echo "node_a not ready after ${TIMEOUT}s"; exit 1; }
wait_up "http://$HOST:$NODE_B_PORT" || { echo "node_b not ready after ${TIMEOUT}s"; exit 1; }
wait_up "http://$HOST:$NODE_C_PORT" || { echo "node_c not ready after ${TIMEOUT}s"; exit 1; }
echo "    All nodes are up."

echo ""
echo "==> Registering peers (using Docker network hostnames)..."
curl -s -X POST "http://$HOST:$NODE_A_PORT/nodes/register" \
  -H 'Content-Type: application/json' \
  -d '{"nodes":["http://node_b:5001","http://node_c:5002"]}' | json_pp || true

curl -s -X POST "http://$HOST:$NODE_B_PORT/nodes/register" \
  -H 'Content-Type: application/json' \
  -d '{"nodes":["http://node_a:5000","http://node_c:5002"]}' | json_pp || true

curl -s -X POST "http://$HOST:$NODE_C_PORT/nodes/register" \
  -H 'Content-Type: application/json' \
  -d '{"nodes":["http://node_a:5000","http://node_b:5001"]}' | json_pp || true

echo ""
echo "==> Fetching node and demo-user addresses..."
NODE_B_ADDR=$(curl -s "http://$HOST:$NODE_B_PORT/node" | json_get '.address')
NODE_C_ADDR=$(curl -s "http://$HOST:$NODE_C_PORT/node" | json_get '.address')
RESPONSABLE_ADDR=$(curl -s "http://$HOST:$NODE_A_PORT/demo/roles" | json_get '.demo_roles.responsable.address')
echo "    node_b      : $NODE_B_ADDR"
echo "    node_c      : $NODE_C_ADDR"
echo "    responsable : $RESPONSABLE_ADDR"

echo ""
echo "==> Registering node_b, node_c, and responsable as authorities on node_a..."
curl -s -X POST "http://$HOST:$NODE_A_PORT/authorities/register" \
  -H 'Content-Type: application/json' \
  -d "{\"address\":\"$NODE_B_ADDR\"}" | json_pp || true

curl -s -X POST "http://$HOST:$NODE_A_PORT/authorities/register" \
  -H 'Content-Type: application/json' \
  -d "{\"address\":\"$NODE_C_ADDR\"}" | json_pp || true

curl -s -X POST "http://$HOST:$NODE_A_PORT/authorities/register" \
  -H 'Content-Type: application/json' \
  -d "{\"address\":\"$RESPONSABLE_ADDR\"}" | json_pp || true

echo ""
echo "==> Mining registration block on node_a..."
curl -s "http://$HOST:$NODE_A_PORT/mine" | json_pp || true

echo ""
echo "==> Syncing chain to node_b and node_c..."
curl -s "http://$HOST:$NODE_B_PORT/nodes/resolve" | json_pp || true
curl -s "http://$HOST:$NODE_C_PORT/nodes/resolve" | json_pp || true

echo ""
echo "==> Network ready."
echo "    node_a : http://$HOST:$NODE_A_PORT"
echo "    node_b : http://$HOST:$NODE_B_PORT"
echo "    node_c : http://$HOST:$NODE_C_PORT"
