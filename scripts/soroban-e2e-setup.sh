#!/usr/bin/env bash
# Deploy soroscan_core to a local standalone quickstart node and emit a test event.
#
# Issue #1218 — ci: add integration test workflow against local Soroban RPC node

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RPC_URL="${SOROBAN_RPC_URL:-http://localhost:8000/rpc}"
NETWORK="${STELLAR_NETWORK_PASSPHRASE:-Standalone Network ; February 2017}"
HORIZON="${HORIZON_URL:-http://localhost:8000}"
NETWORK_NAME="${STELLAR_NETWORK_NAME:-local}"
IDENTITY="${STELLAR_IDENTITY:-e2e-admin}"
CONTRACT_FILE="$REPO_ROOT/.soroban-e2e-contract-id"

echo "[soroban-e2e] Waiting for quickstart health at ${HORIZON}/health ..."
for _ in $(seq 1 90); do
  if curl -sf "${HORIZON}/health" >/dev/null 2>&1; then
    break
  fi
  sleep 2
done
curl -sf "${HORIZON}/health" >/dev/null

echo "[soroban-e2e] Configuring Stellar CLI network ${NETWORK_NAME}"
stellar network add "${NETWORK_NAME}" \
  --rpc-url "${RPC_URL}" \
  --network-passphrase "${NETWORK}" \
  2>/dev/null || true

echo "[soroban-e2e] Ensuring Stellar identity ${IDENTITY}"
if ! stellar keys address "${IDENTITY}" >/dev/null 2>&1; then
  stellar keys generate "${IDENTITY}" --network "${NETWORK_NAME}"
fi
ADDR="$(stellar keys address "${IDENTITY}")"

echo "[soroban-e2e] Funding ${ADDR} via friendbot"
FUNDED=false
for _ in $(seq 1 30); do
  if curl -sf "${HORIZON}/accounts/${ADDR}" >/dev/null 2>&1; then
    FUNDED=true
    echo "[soroban-e2e] Account ${ADDR} is funded"
    break
  fi
  curl -sf "${HORIZON}/friendbot?addr=${ADDR}" >/dev/null 2>&1 || \
    stellar keys fund "${IDENTITY}" --network "${NETWORK_NAME}" >/dev/null 2>&1 || true
  sleep 3
done

if [ "$FUNDED" = false ]; then
  for _ in $(seq 1 15); do
    if curl -sf "${HORIZON}/accounts/${ADDR}" >/dev/null 2>&1; then
      FUNDED=true
      echo "[soroban-e2e] Account ${ADDR} is funded"
      break
    fi
    sleep 2
  done
fi

if [ "$FUNDED" = false ]; then
  echo "[soroban-e2e] ERROR: account ${ADDR} was not funded"
  exit 1
fi

echo "[soroban-e2e] Building soroscan_core.wasm (Rust 1.85, baseline wasm CPU: 1.82+ otherwise emits reference-types, which soroban-sdk 21 hosts reject)"
cd "${REPO_ROOT}/soroban-contracts/soroscan_core"
RUSTFLAGS="${RUSTFLAGS:-} -C target-cpu=mvp" cargo build --target wasm32-unknown-unknown --release

WASM="target/wasm32-unknown-unknown/release/soroscan_core.wasm"

echo "[soroban-e2e] Deploying contract"
DEPLOY_OUTPUT="$(stellar contract deploy \
  --wasm "${WASM}" \
  --source "${IDENTITY}" \
  --rpc-url "${RPC_URL}" \
  --network-passphrase "${NETWORK}")"
CONTRACT_ID="$(echo "${DEPLOY_OUTPUT}" | awk '{print $NF}')"
echo "${CONTRACT_ID}" > "${CONTRACT_FILE}"
echo "[soroban-e2e] Deployed contract id: ${CONTRACT_ID}"

if [ -n "${GITHUB_ENV:-}" ]; then
  echo "SOROSCAN_CONTRACT_ID=${CONTRACT_ID}" >> "${GITHUB_ENV}"
fi

echo "[soroban-e2e] Initializing contract"
stellar contract invoke \
  --id "${CONTRACT_ID}" \
  --source "${IDENTITY}" \
  --rpc-url "${RPC_URL}" \
  --network-passphrase "${NETWORK}" \
  -- init --admin "${ADDR}"

echo "[soroban-e2e] Authorizing indexer"
stellar contract invoke \
  --id "${CONTRACT_ID}" \
  --source "${IDENTITY}" \
  --rpc-url "${RPC_URL}" \
  --network-passphrase "${NETWORK}" \
  -- add_indexer --admin "${ADDR}" --indexer "${ADDR}"

PAYLOAD_HASH="0000000000000000000000000000000000000000000000000000000000000000"

echo "[soroban-e2e] Recording live Soroban event"
stellar contract invoke \
  --id "${CONTRACT_ID}" \
  --source "${IDENTITY}" \
  --rpc-url "${RPC_URL}" \
  --network-passphrase "${NETWORK}" \
  -- record_event \
  --indexer "${ADDR}" \
  --contract_id "${ADDR}" \
  --event_type transfer \
  --payload_hash "${PAYLOAD_HASH}"

echo "[soroban-e2e] Setup complete"
