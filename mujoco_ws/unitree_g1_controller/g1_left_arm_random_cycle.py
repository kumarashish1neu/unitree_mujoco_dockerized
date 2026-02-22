#!/usr/bin/env python3
"""Launch RL-MJLab G1 deploy controller using a trained checkpoint export.

This script is used by `unitree_mujoco_dockerized` as the "controller" process.
It does not implement low-level control itself; instead it:
1) finds a trained policy export from `/workspace/checkpoints`
2) builds a temporary RL-MJLab deploy config bundle
3) starts `deploy/robots/g1/build/g1_ctrl` in Velocity mode
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import yaml


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--interface", default=os.environ.get("INTERFACE", "lo"))
    parser.add_argument(
        "--domain-id",
        type=int,
        default=int(os.environ.get("DOMAIN_ID", "0")),
        help="Accepted for compatibility; g1_ctrl currently hardcodes DDS domain 0.",
    )
    parser.add_argument(
        "--rlmjlab-root",
        default=os.environ.get("RLMJLAB_ROOT", "/opt/unitree_rl_mjlab"),
        help="Path to unitree_rl_mjlab repository (contains deploy/robots/g1).",
    )
    parser.add_argument(
        "--deploy-binary",
        default="",
        help="Optional explicit path to g1_ctrl binary. If omitted, common paths are searched.",
    )
    parser.add_argument(
        "--checkpoint-root",
        default=os.environ.get(
            "RLMJLAB_CHECKPOINT_ROOT", "/workspace/checkpoints"
        ),
        help="Root directory mounted into the container (default: /workspace/checkpoints).",
    )
    parser.add_argument(
        "--checkpoint-file",
        default="",
        help="Explicit checkpoint exported ONNX path or a run-local policy.onnx path.",
    )
    parser.add_argument(
        "--checkpoint-run",
        default="",
        help="Relative run path under checkpoint root (e.g. rsl_rl/g1_velocity/<run>).",
    )
    parser.add_argument(
        "--task-family",
        default="velocity",
        choices=["velocity", "mimic"],
        help="Selects deploy policy template params/deploy.yaml to pair with exported ONNX.",
    )
    parser.add_argument(
        "--start-state",
        default="Velocity",
        help="FSM state to place first in config so controller starts immediately in that state.",
    )
    return parser.parse_args()


def _find_deploy_binary(explicit: str, rlmjlab_root: Path) -> Path:
    candidates = []
    if explicit:
        candidates.append(Path(explicit))
    candidates.extend(
        [
            rlmjlab_root / "deploy/robots/g1/build/g1_ctrl",
            Path("/opt/unitree_rl_mjlab/deploy/robots/g1/build/g1_ctrl"),
            Path("/workspace/unitree_rl_mjlab/deploy/robots/g1/build/g1_ctrl"),
        ]
    )
    for path in candidates:
        if path.exists() and os.access(path, os.X_OK):
            return path
    raise FileNotFoundError(
        "Deploy binary not found. Checked:\n  - " + "\n  - ".join(str(p) for p in candidates)
    )


def _resolve_checkpoint_onnx(args: argparse.Namespace) -> Path:
    if args.checkpoint_file:
        p = Path(args.checkpoint_file)
        if p.is_dir():
            p = p / "policy.onnx"
        if not p.exists():
            raise FileNotFoundError(f"Checkpoint file not found: {p}")
        return p.resolve()

    root = Path(args.checkpoint_root)
    if not root.exists():
        raise FileNotFoundError(f"Checkpoint root not found: {root}")

    if args.checkpoint_run:
        run_dir = root / args.checkpoint_run
        onnx_path = run_dir / "policy.onnx"
        if not onnx_path.exists():
            raise FileNotFoundError(f"policy.onnx not found in run dir: {run_dir}")
        return onnx_path.resolve()

    run_root = root / "rsl_rl" / "g1_velocity"
    if not run_root.exists():
        raise FileNotFoundError(
            f"No velocity runs found. Expected directory: {run_root}. "
            "Pass --checkpoint-file or --checkpoint-run."
        )

    run_dirs = sorted([p for p in run_root.iterdir() if p.is_dir()])
    for run_dir in reversed(run_dirs):
        onnx_path = run_dir / "policy.onnx"
        if onnx_path.exists():
            return onnx_path.resolve()

    raise FileNotFoundError(
        f"No exported policy.onnx found under {run_root}. "
        "Train/export first in unitree_rl_mjlab_dockerized."
    )


def _copy_if_exists(src: Path, dst: Path) -> None:
    if src.exists():
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)


def _reorder_enabled_fsms(config_data: dict, start_state: str) -> dict:
    fsm = config_data.get("FSM")
    if not isinstance(fsm, dict):
        raise RuntimeError("Invalid deploy config: missing FSM map")
    enabled = fsm.get("_")
    if not isinstance(enabled, dict):
        raise RuntimeError("Invalid deploy config: missing FSM._ map")
    if start_state not in enabled:
        raise RuntimeError(
            f"Requested start state '{start_state}' not present in FSM._ ({list(enabled.keys())})"
        )

    if next(iter(enabled.keys())) == start_state:
        return config_data

    reordered = {start_state: enabled[start_state]}
    for key, value in enabled.items():
        if key != start_state:
            reordered[key] = value
    fsm["_"] = reordered
    return config_data


def _prepare_runtime_bundle(
    rlmjlab_root: Path, deploy_binary: Path, onnx_path: Path, start_state: str, task_family: str
) -> tuple[Path, Path]:
    g1_root = rlmjlab_root / "deploy/robots/g1"
    src_config_dir = g1_root / "config"
    if not src_config_dir.exists():
        raise FileNotFoundError(f"Deploy config directory not found: {src_config_dir}")

    tmp_root = Path(tempfile.mkdtemp(prefix="g1_rlmjlab_runtime_"))
    proj_dir = tmp_root / "g1"
    build_dir = proj_dir / "build"
    config_dir = proj_dir / "config"
    build_dir.mkdir(parents=True, exist_ok=True)

    # Copy the binary (not symlink) so /proc/self/exe resolves inside this temp project.
    runtime_binary = build_dir / "g1_ctrl"
    shutil.copy2(deploy_binary, runtime_binary)
    runtime_binary.chmod(0o755)

    shutil.copytree(src_config_dir, config_dir)

    # Create a deploy policy bundle from the trained checkpoint export.
    policy_variant_dir = config_dir / "policy" / task_family / "trained_from_checkpoint"
    (policy_variant_dir / "exported").mkdir(parents=True, exist_ok=True)
    (policy_variant_dir / "params").mkdir(parents=True, exist_ok=True)
    shutil.copy2(onnx_path, policy_variant_dir / "exported" / "policy.onnx")
    _copy_if_exists(onnx_path.with_suffix(".onnx.data"), policy_variant_dir / "exported" / "policy.onnx.data")
    _copy_if_exists(onnx_path.with_name(onnx_path.name + ".data"), policy_variant_dir / "exported" / "policy.onnx.data")

    if task_family == "velocity":
        template_deploy_yaml = src_config_dir / "policy" / "velocity" / "v0" / "params" / "deploy.yaml"
    else:
        template_deploy_yaml = src_config_dir / "policy" / "mimic" / "dance1_subject2" / "params" / "deploy.yaml"
    if not template_deploy_yaml.exists():
        raise FileNotFoundError(f"Template deploy.yaml not found: {template_deploy_yaml}")
    shutil.copy2(template_deploy_yaml, policy_variant_dir / "params" / "deploy.yaml")

    config_yaml_path = config_dir / "config.yaml"
    with open(config_yaml_path, "r", encoding="utf-8") as f:
        config_data = yaml.safe_load(f)
    config_data = _reorder_enabled_fsms(config_data, start_state=start_state)
    if "FSM" in config_data and start_state in config_data["FSM"]:
        if start_state == "Velocity":
            config_data["FSM"][start_state]["policy_dir"] = "config/policy/velocity/trained_from_checkpoint"
        elif "policy_dir" in config_data["FSM"][start_state]:
            config_data["FSM"][start_state]["policy_dir"] = f"config/policy/{task_family}/trained_from_checkpoint"
    with open(config_yaml_path, "w", encoding="utf-8") as f:
        yaml.safe_dump(config_data, f, sort_keys=False)

    return runtime_binary, proj_dir


def main() -> int:
    args = _parse_args()

    if args.domain_id != 0:
        print(
            f"[WARN] --domain-id={args.domain_id} was provided, but RL-MJLab g1_ctrl hardcodes DDS domain 0. "
            "Set simulator DOMAIN_ID=0 for communication.",
            flush=True,
        )

    rlmjlab_root = Path(args.rlmjlab_root).resolve()
    deploy_binary = _find_deploy_binary(args.deploy_binary, rlmjlab_root)
    onnx_path = _resolve_checkpoint_onnx(args)

    print(f"[INFO] Using RL-MJLab root: {rlmjlab_root}", flush=True)
    print(f"[INFO] Using deploy binary: {deploy_binary}", flush=True)
    print(f"[INFO] Using checkpoint export: {onnx_path}", flush=True)

    runtime_binary, proj_dir = _prepare_runtime_bundle(
        rlmjlab_root=rlmjlab_root,
        deploy_binary=deploy_binary,
        onnx_path=onnx_path,
        start_state=args.start_state,
        task_family=args.task_family,
    )
    print(f"[INFO] Prepared runtime deploy project: {proj_dir}", flush=True)

    cmd = [str(runtime_binary), "--network", args.interface]
    print("[INFO] Launching: " + " ".join(cmd), flush=True)

    try:
        return subprocess.call(cmd, cwd=str(proj_dir))
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    sys.exit(main())
