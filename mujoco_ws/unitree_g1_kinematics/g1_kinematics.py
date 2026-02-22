#!/usr/bin/env python3
"""G1 kinematics helper (DDS/SDK snapshot -> fingertip poses)."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from yourdfpy import URDF

UNITREE_ROS_G1_DESCRIPTION_DIR = Path("/workspace/unitree_ros/robots/g1_description")
UNITREE_ROS_G1_DEFAULT_URDF = UNITREE_ROS_G1_DESCRIPTION_DIR / "g1_29dof.urdf"
DEFAULT_FINGERTIP_LINKS = ("left_rubber_hand", "right_rubber_hand")


@dataclass
class JointStateSnapshot:
    joint_positions: dict[str, float] = field(default_factory=dict)
    timestamp_sec: float | None = None
    frame: str = "world"


class G1Kinematics:
    def __init__(
        self,
        urdf_path: str | Path | None = None,
        fingertip_links: tuple[str, str] = DEFAULT_FINGERTIP_LINKS,
    ) -> None:
        self.urdf_path = Path(urdf_path).expanduser().resolve() if urdf_path else None
        self.fingertip_links = fingertip_links
        self.mujoco_to_urdf_joint_map: dict[str, str] = {}
        self.urdf = None  # yourdfpy.URDF instance (lazy-loaded type)

        if self.urdf_path is not None:
            self.load_urdf(self.urdf_path)

    @staticmethod
    def default_unitree_ros_g1_urdf_path() -> Path:
        if not UNITREE_ROS_G1_DEFAULT_URDF.exists():
            raise FileNotFoundError(f"Expected G1 URDF not found: {UNITREE_ROS_G1_DEFAULT_URDF}")
        return UNITREE_ROS_G1_DEFAULT_URDF

    def load_urdf(self, urdf_path: str | Path) -> None:
        path = Path(urdf_path).expanduser().resolve()
        if not path.exists():
            raise FileNotFoundError(f"URDF not found: {path}")

        # Build scene graph for FK transforms but skip mesh loading.
        self.urdf = URDF.load(
            str(path),
            build_scene_graph=True,
            build_collision_scene_graph=False,
            load_meshes=False,
            load_collision_meshes=False,
        )
        self.urdf_path = path

    def set_joint_name_map(self, mapping: dict[str, str]) -> None:
        self.mujoco_to_urdf_joint_map = dict(mapping)

    def list_joint_names(self) -> list[str]:
        self._require_urdf()
        return [j.name for j in self.urdf.robot.joints]

    def list_link_names(self) -> list[str]:
        self._require_urdf()
        return [l.name for l in self.urdf.robot.links]

    def get_joint_info(self, joint_name: str) -> dict[str, Any]:
        """Return a compact metadata dict for a URDF joint."""
        self._require_urdf()
        joint = self.urdf.joint_map[joint_name]
        origin = joint.origin
        origin_xyz = (
            (float(origin[0, 3]), float(origin[1, 3]), float(origin[2, 3]))
            if origin is not None
            else (0.0, 0.0, 0.0)
        )
        axis = joint.axis if joint.axis is not None else (0.0, 0.0, 0.0)
        limit = joint.limit
        return {
            "name": joint.name,
            "type": joint.type,
            "parent": joint.parent,
            "child": joint.child,
            "origin_xyz": origin_xyz,
            "axis_xyz": (float(axis[0]), float(axis[1]), float(axis[2])),
            "limit_lower": None if limit is None else limit.lower,
            "limit_upper": None if limit is None else limit.upper,
            "limit_effort": None if limit is None else limit.effort,
            "limit_velocity": None if limit is None else limit.velocity,
        }

    def get_joint_offset_lengths(self) -> dict[str, float]:
        """Useful proxy for segment lengths: norm of each joint's origin translation."""
        self._require_urdf()
        out: dict[str, float] = {}
        for j in self.urdf.robot.joints:
            info = self.get_joint_info(j.name)
            x, y, z = info["origin_xyz"]
            out[j.name] = (x * x + y * y + z * z) ** 0.5
        return out

    def fingertip_poses_from_snapshot(
        self,
        snapshot: JointStateSnapshot,
        frame_from: str | None = None,
    ) -> dict[str, Any]:
        self._require_urdf()
        joint_cfg = self._map_joint_names(snapshot.joint_positions)
        self.urdf.update_cfg(joint_cfg)

        poses: dict[str, Any] = {}
        for link_name in self.fingertip_links:
            poses[link_name] = self.urdf.get_transform(frame_to=link_name, frame_from=frame_from)
        return poses

    def _map_joint_names(self, joint_positions: dict[str, float]) -> dict[str, float]:
        return {
            self.mujoco_to_urdf_joint_map.get(name, name): value
            for name, value in joint_positions.items()
        }

    def _require_urdf(self) -> None:
        if self.urdf is None:
            raise RuntimeError("URDF not loaded. Call load_urdf(...) first.")
