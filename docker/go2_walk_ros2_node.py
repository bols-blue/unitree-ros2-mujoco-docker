#!/usr/bin/env python3
"""go2_rl_gym の学習済み歩行ポリシーを、ROS2トピック(/lowstate, /lowcmd)経由で
unitree_mujoco上のGo2に適用するブリッジノード。

deploy/deploy_mujoco/deploy_go2.py (go2_rl_gym) と違い、mujocoのPythonバインディング
やプロセス内物理演算には一切アクセスしない。すべてDDS(ROS2トピック)越しにやりとりする
ので、C++の unitree_mujoco シミュレータ + rmw_cyclonedds を介したふつうのROS2ノードとして
動く(ROS2ツール - ros2 topic, rosbag, rviz等 - から見える/触れる)。

/cmd_vel (geometry_msgs/Twist) を購読し、teleop_twist_keyboard 等からの速度指令で
歩行方向・速度をリアルタイムに変更できる。

前提:
- 別シェルで /opt/run_mujoco.sh -r go2 -s scene_terrain.xml が起動していること
- このノードは ROS2 (source /opt/setup_env.sh) をsourceしたシェルで実行すること
"""
import os

import numpy as np
import rclpy
import torch
import yaml
from geometry_msgs.msg import Twist
from rclpy.node import Node
from unitree_go.msg import LowCmd, LowState

from legged_gym import LEGGED_GYM_ROOT_DIR

CONFIG_PATH = f"{LEGGED_GYM_ROOT_DIR}/deploy/deploy_mujoco/configs/go2.yaml"

# unitree_go の LowCmd/LowState 内 motor_[cmd|state][0..11] の並び順
# (unitree_mujoco の actuator 順=DDSのモーター順。ビルド時ログで確認済み)
DDS_JOINT_NAMES = [
    "FR_hip_joint", "FR_thigh_joint", "FR_calf_joint",
    "FL_hip_joint", "FL_thigh_joint", "FL_calf_joint",
    "RR_hip_joint", "RR_thigh_joint", "RR_calf_joint",
    "RL_hip_joint", "RL_thigh_joint", "RL_calf_joint",
]


def get_gravity_orientation(quaternion):
    qw, qx, qy, qz = quaternion
    g = np.zeros(3, dtype=np.float32)
    g[0] = 2 * (-qz * qx + qw * qy)
    g[1] = -2 * (qz * qy + qw * qx)
    g[2] = 1 - 2 * (qw * qw + qz * qz)
    return g


class Go2WalkRos2Node(Node):
    def __init__(self):
        super().__init__("go2_walk_ros2")

        with open(CONFIG_PATH, "r") as f:
            cfg = yaml.load(f, Loader=yaml.FullLoader)

        policy_path = cfg["policy_path"].replace("{LEGGED_GYM_ROOT_DIR}", LEGGED_GYM_ROOT_DIR)
        self.control_dt = cfg["simulation_dt"] * cfg["control_decimation"]
        self.kps = np.array(cfg["kps"], dtype=np.float32)
        self.kds = np.array(cfg["kds"], dtype=np.float32)
        self.default_angles = np.array(cfg["default_angles"], dtype=np.float32)
        self.ang_vel_scale = cfg["ang_vel_scale"]
        self.dof_pos_scale = cfg["dof_pos_scale"]
        self.dof_vel_scale = cfg["dof_vel_scale"]
        self.action_scale = cfg["action_scale"]
        self.cmd_scale = np.array(cfg["cmd_scale"], dtype=np.float32)
        self.num_actions = cfg["num_actions"]
        self.num_obs = cfg["num_obs"]
        self.max_cmd = np.array(cfg["max_cmd"], dtype=np.float32)
        self.cmd = np.array(cfg["cmd_init"], dtype=np.float32)

        model_joint_names = cfg["model_joint_names"]
        # arr_dds[idx_dds2model] で dds順配列 -> model順配列に変換できるようにする
        # (dds順配列の「model_joint_names[i]番目の関節」がどこにあるかを表引き)
        self.idx_dds2model = [DDS_JOINT_NAMES.index(n) for n in model_joint_names]
        self.idx_model2dds = [model_joint_names.index(n) for n in DDS_JOINT_NAMES]

        self.get_logger().info(f"Loading policy: {policy_path}")
        self.policy = torch.jit.load(policy_path)

        self.action = np.zeros(self.num_actions, dtype=np.float32)
        self.target_dof_pos = self.default_angles.copy()
        self.obs = np.zeros(self.num_obs, dtype=np.float32)
        self.have_state = False

        self.last_infer_time = None
        self.sub = self.create_subscription(LowState, "/lowstate", self._on_lowstate, 10)
        self.pub = self.create_publisher(LowCmd, "/lowcmd", 10)
        self.cmd_vel_sub = self.create_subscription(Twist, "/cmd_vel", self._on_cmd_vel, 10)
        self.get_logger().info(
            f"go2_walk_ros2 ready. control_dt={self.control_dt:.3f}s cmd={self.cmd.tolist()}"
            " (/cmd_vel で上書き可能。teleop_twist_keyboard等を使用)"
        )

    def _on_cmd_vel(self, msg: Twist):
        cmd = np.array([msg.linear.x, msg.linear.y, msg.angular.z], dtype=np.float32)
        self.cmd = np.clip(cmd, -self.max_cmd, self.max_cmd)

    def _on_lowstate(self, msg: LowState):
        # /lowstate は ~800-1000Hz で届く。独立タイマーで別に間引くと発行位相がずれて
        # 余分な遅延・ジッタが乗り、歩行ポリシーが不安定になる(実測で確認済み)。
        # 受信コールバック内で経過時間を見て直接間引く方が遅延が小さく安定する。
        now = self.get_clock().now().nanoseconds * 1e-9
        if self.last_infer_time is not None and (now - self.last_infer_time) < self.control_dt:
            self.last_msg = msg
            return
        self.last_infer_time = now

        qj_dds = np.array([msg.motor_state[i].q for i in range(12)], dtype=np.float32)
        dqj_dds = np.array([msg.motor_state[i].dq for i in range(12)], dtype=np.float32)
        qj = qj_dds[self.idx_dds2model]
        dqj = dqj_dds[self.idx_dds2model]

        quat = msg.imu_state.quaternion  # [w, x, y, z]
        ang_vel = np.array(msg.imu_state.gyroscope, dtype=np.float32)

        qj_obs = (qj - self.default_angles) * self.dof_pos_scale
        dqj_obs = dqj * self.dof_vel_scale
        gravity_orientation = get_gravity_orientation(quat)
        ang_vel_obs = ang_vel * self.ang_vel_scale

        self.obs[0:3] = ang_vel_obs
        self.obs[3:6] = gravity_orientation
        self.obs[6:9] = self.cmd * self.cmd_scale
        self.obs[9:9 + self.num_actions] = qj_obs
        self.obs[9 + self.num_actions:9 + 2 * self.num_actions] = dqj_obs
        self.obs[9 + 2 * self.num_actions:9 + 3 * self.num_actions] = self.action

        obs_tensor = torch.from_numpy(self.obs).unsqueeze(0)
        result = self.policy(obs_tensor)
        if isinstance(result, tuple):
            action = result[0].detach().numpy().squeeze()
        else:
            action = result.detach().numpy().squeeze()
        self.action = action
        self.target_dof_pos = action * self.action_scale + self.default_angles

        target_dds = self.target_dof_pos[self.idx_model2dds]
        kps_dds = self.kps[self.idx_model2dds]
        kds_dds = self.kds[self.idx_model2dds]

        cmd_msg = LowCmd()
        for i in range(12):
            cmd_msg.motor_cmd[i].mode = 0x01
            cmd_msg.motor_cmd[i].q = float(target_dds[i])
            cmd_msg.motor_cmd[i].dq = 0.0
            cmd_msg.motor_cmd[i].tau = 0.0
            cmd_msg.motor_cmd[i].kp = float(kps_dds[i])
            cmd_msg.motor_cmd[i].kd = float(kds_dds[i])
        self.pub.publish(cmd_msg)


def main():
    rclpy.init()
    node = Go2WalkRos2Node()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
