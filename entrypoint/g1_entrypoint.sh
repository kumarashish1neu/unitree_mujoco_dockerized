#!/usr/bin/env bash
set -euo pipefail

SIM_DIR="/workspace/unitree_mujoco/simulate_python"
SIM_SCRIPT="${SIM_DIR}/unitree_mujoco.py"
SIM_CONFIG="${SIM_DIR}/config.py"

ROBOT="${ROBOT:-g1}"
ROBOT_SCENE="${ROBOT_SCENE:-/workspace/unitree_mujoco/unitree_robots/${ROBOT}/scene.xml}"
DOMAIN_ID="${DOMAIN_ID:-1}"
INTERFACE="${INTERFACE:-lo}"
USE_JOYSTICK="${USE_JOYSTICK:-0}"
JOYSTICK_TYPE="${JOYSTICK_TYPE:-xbox}"
JOYSTICK_DEVICE="${JOYSTICK_DEVICE:-0}"
PRINT_SCENE_INFORMATION="${PRINT_SCENE_INFORMATION:-true}"
ENABLE_ELASTIC_BAND="${ENABLE_ELASTIC_BAND:-false}"

if [ ! -f "${SIM_SCRIPT}" ]; then
    echo "Simulator script not found: ${SIM_SCRIPT}"
    exit 1
fi

cat > "${SIM_CONFIG}" <<EOF
import os

ROBOT = "${ROBOT}"
ROBOT_SCENE = "${ROBOT_SCENE}"
DOMAIN_ID = int("${DOMAIN_ID}")
INTERFACE = "${INTERFACE}"
USE_JOYSTICK = int("${USE_JOYSTICK}")
JOYSTICK_TYPE = "${JOYSTICK_TYPE}"
JOYSTICK_DEVICE = int("${JOYSTICK_DEVICE}")
PRINT_SCENE_INFORMATION = "${PRINT_SCENE_INFORMATION}".lower() == "true"
ENABLE_ELASTIC_BAND = "${ENABLE_ELASTIC_BAND}".lower() == "true"
SIMULATE_DT = 0.005
VIEWER_DT = 0.02
EOF

echo "[entrypoint] Starting simulator: ${SIM_SCRIPT}"
python3 "${SIM_SCRIPT}" &
SIM_PID=$!

CTRL_PID=""
if [ "$#" -gt 0 ]; then
    echo "[entrypoint] Starting controller command: $*"
    if [[ "$1" == *.py ]]; then
        python3 "$@" &
    else
        "$@" &
    fi
    CTRL_PID=$!
fi

cleanup() {
    set +e
    if [ -n "${CTRL_PID}" ] && kill -0 "${CTRL_PID}" 2>/dev/null; then
        kill "${CTRL_PID}" 2>/dev/null || true
    fi
    if kill -0 "${SIM_PID}" 2>/dev/null; then
        kill "${SIM_PID}" 2>/dev/null || true
    fi
    wait "${CTRL_PID}" 2>/dev/null || true
    wait "${SIM_PID}" 2>/dev/null || true
}

trap cleanup INT TERM

wait "${SIM_PID}"
SIM_STATUS=$?

if [ -n "${CTRL_PID}" ] && kill -0 "${CTRL_PID}" 2>/dev/null; then
    kill "${CTRL_PID}" 2>/dev/null || true
    wait "${CTRL_PID}" 2>/dev/null || true
fi

exit "${SIM_STATUS}"
