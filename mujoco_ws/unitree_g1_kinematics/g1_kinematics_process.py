#!/usr/bin/env python3
"""Separate-process G1 kinematics subscriber (DDS lowstate -> named joint snapshot)."""

import argparse
import os
import time
from pathlib import Path

from g1_kinematics import G1Kinematics, JointStateSnapshot

from unitree_sdk2py.core.channel import ChannelSubscriber, ChannelFactoryInitialize
from unitree_sdk2py.idl.unitree_hg.msg.dds_ import LowState_

TOPIC_LOWSTATE = "rt/lowstate"

# G1 29DOF actuator order published by the simulator bridge (`motor_state[i]`)
G1_MOTOR_INDEX_TO_URDF_JOINT = [
    "left_hip_pitch_joint",
    "left_hip_roll_joint",
    "left_hip_yaw_joint",
    "left_knee_joint",
    "left_ankle_pitch_joint",
    "left_ankle_roll_joint",
    "right_hip_pitch_joint",
    "right_hip_roll_joint",
    "right_hip_yaw_joint",
    "right_knee_joint",
    "right_ankle_pitch_joint",
    "right_ankle_roll_joint",
    "waist_yaw_joint",
    "waist_roll_joint",
    "waist_pitch_joint",
    "left_shoulder_pitch_joint",
    "left_shoulder_roll_joint",
    "left_shoulder_yaw_joint",
    "left_elbow_joint",
    "left_wrist_roll_joint",
    "left_wrist_pitch_joint",
    "left_wrist_yaw_joint",
    "right_shoulder_pitch_joint",
    "right_shoulder_roll_joint",
    "right_shoulder_yaw_joint",
    "right_elbow_joint",
    "right_wrist_roll_joint",
    "right_wrist_pitch_joint",
    "right_wrist_yaw_joint",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--urdf",
        default=os.environ.get("KINEMATICS_URDF", ""),
        help="Optional URDF path to load on startup. Defaults to unitree_ros G1 description in container.",
    )
    parser.add_argument(
        "--period-sec",
        type=float,
        default=float(os.environ.get("KINEMATICS_PERIOD_SEC", "1.0")),
        help="Polling/compute loop period.",
    )
    parser.add_argument(
        "--interface",
        default=os.environ.get("INTERFACE", "lo"),
        help="DDS network interface",
    )
    parser.add_argument(
        "--domain-id",
        type=int,
        default=int(os.environ.get("DOMAIN_ID", "0")),
        help="DDS domain id (must match simulator/bridge)",
    )
    return parser.parse_args()


class LowStateReader:
    def __init__(self) -> None:
        self.latest_msg: LowState_ | None = None
        self.update_count = 0
        self.sub: ChannelSubscriber | None = None

    def on_lowstate(self, msg: LowState_) -> None:
        self.latest_msg = msg
        self.update_count += 1

    def init(self) -> None:
        self.sub = ChannelSubscriber(TOPIC_LOWSTATE, LowState_)
        self.sub.Init(self.on_lowstate, 10)

    def snapshot(self) -> JointStateSnapshot | None:
        msg = self.latest_msg
        if msg is None:
            return None
        joint_positions = {
            joint_name: float(msg.motor_state[i].q)
            for i, joint_name in enumerate(G1_MOTOR_INDEX_TO_URDF_JOINT)
        }
        return JointStateSnapshot(joint_positions=joint_positions)


def on_joint_snapshot(kin: G1Kinematics, snapshot: JointStateSnapshot) -> None:
    """Hook for user FK code.

    Replace/extend this function with your forward-kinematics logic.
    Example:
      poses = kin.fingertip_poses_from_snapshot(snapshot)
    """
    del kin
    _ = snapshot


def main() -> int:
    args = parse_args()

    if args.urdf:
        urdf_path = Path(args.urdf).expanduser().resolve()
    else:
        urdf_path = G1Kinematics.default_unitree_ros_g1_urdf_path()
    kin = G1Kinematics(urdf_path=urdf_path)
    reader = LowStateReader()

    ChannelFactoryInitialize(args.domain_id, args.interface)
    reader.init()

    print("[kinematics] G1 kinematics process started.", flush=True)
    print(f"[kinematics] URDF loaded: {bool(kin.urdf_path)}", flush=True)
    if kin.urdf_path:
        print(f"[kinematics] URDF path: {kin.urdf_path}", flush=True)
    print(f"[kinematics] DDS topic: {TOPIC_LOWSTATE}", flush=True)
    print(f"[kinematics] DDS domain/interface: {args.domain_id}/{args.interface}", flush=True)
    print("[kinematics] Waiting for lowstate...", flush=True)

    while True:
        snapshot = reader.snapshot()
        if snapshot is not None:
            on_joint_snapshot(kin, snapshot)
        time.sleep(max(args.period_sec, 0.01))


if __name__ == "__main__":
    raise SystemExit(main())
