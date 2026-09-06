#!/usr/bin/env python3
"""unitree_mujoco(C++)上で動いているGo2の姿勢を/sportmodestateと/lowstateから
再構成し、同じシーン(scene_terrain.xml)を読み込んだ「物理演算はしないシャドー用の
MjModel/MjData」に反映したうえでmj_ray()でレイキャストし、疑似3D走査LiDAR
(Velodyne VLP-16相当: 垂直16chの回転式)をシミュレートするROS2ノード。

unitree_mujoco(C++)のプロセス内部データには一切アクセスしない。ROS2トピック経由で
受け取った姿勢をそっくりそのまま同じシーンXML上で再現し、そのシーン上でレイキャスト
するだけなので地形(このシーンの静的ジオメトリ)に対する距離は物理シミュレータ本体と
一致するが、実機のUnitree L1(独自の非回転式3D走査パターン)を再現したものではなく、
ロボット搭載点まわりの理想化された等間隔垂直チャンネル走査(ノイズなし)である点に注意。

前提:
- 別シェルで /opt/run_mujoco.sh -r go2 -s scene_terrain.xml が起動していること
- このノードは ROS2 (source /opt/setup_env.sh) をsourceしたシェルで実行すること
"""
import mujoco
import numpy as np
import rclpy
from geometry_msgs.msg import TransformStamped
from rclpy.node import Node
from sensor_msgs.msg import PointCloud2
from sensor_msgs_py import point_cloud2
from std_msgs.msg import Header
from tf2_ros import TransformBroadcaster
from unitree_go.msg import LowState, SportModeState

GO2_SCENE = "/opt/unitree_mujoco/unitree_robots/go2/scene_terrain.xml"

# go2.xml中の<joint>出現順(mujocoのqpos[7:19]順)
MODEL_JOINT_NAMES = [
    "FL_hip_joint", "FL_thigh_joint", "FL_calf_joint",
    "FR_hip_joint", "FR_thigh_joint", "FR_calf_joint",
    "RL_hip_joint", "RL_thigh_joint", "RL_calf_joint",
    "RR_hip_joint", "RR_thigh_joint", "RR_calf_joint",
]
# unitree_go の LowState.motor_state[0..11] の並び順 (go2_walk_ros2_node.py と同じ)
DDS_JOINT_NAMES = [
    "FR_hip_joint", "FR_thigh_joint", "FR_calf_joint",
    "FL_hip_joint", "FL_thigh_joint", "FL_calf_joint",
    "RR_hip_joint", "RR_thigh_joint", "RR_calf_joint",
    "RL_hip_joint", "RL_thigh_joint", "RL_calf_joint",
]
IDX_DDS2MODEL = [DDS_JOINT_NAMES.index(n) for n in MODEL_JOINT_NAMES]

# VLP-16相当のデフォルトパラメータ
NUM_HORIZONTAL = 360
NUM_VERTICAL = 16
ELEVATION_MIN = np.radians(-15.0)
ELEVATION_MAX = np.radians(15.0)
MAX_RANGE = 8.0  # m
# base_link原点からのLiDAR搭載オフセット(本体上面あたりの近似値。実機L1の正確な搭載位置ではない)
MOUNT_OFFSET_BODY = np.array([0.0, 0.0, 0.12])
SCAN_RATE_HZ = 10.0
# ロボット本体(visual=group2, collision=group3)を無視し、地形(group0)だけをレイキャスト対象にする
TERRAIN_GEOMGROUP = np.array([1, 0, 0, 0, 0, 0], dtype=np.uint8)


def quat_to_rotmat(qw, qx, qy, qz):
    return np.array([
        [1 - 2 * (qy * qy + qz * qz), 2 * (qx * qy - qz * qw), 2 * (qx * qz + qy * qw)],
        [2 * (qx * qy + qz * qw), 1 - 2 * (qx * qx + qz * qz), 2 * (qy * qz - qx * qw)],
        [2 * (qx * qz - qy * qw), 2 * (qy * qz + qx * qw), 1 - 2 * (qx * qx + qy * qy)],
    ])


def make_scan_directions():
    az = np.linspace(-np.pi, np.pi, NUM_HORIZONTAL, endpoint=False)
    el = np.linspace(ELEVATION_MIN, ELEVATION_MAX, NUM_VERTICAL)
    az_grid, el_grid = np.meshgrid(az, el)
    dirs = np.stack(
        [np.cos(el_grid) * np.cos(az_grid), np.cos(el_grid) * np.sin(az_grid), np.sin(el_grid)],
        axis=-1,
    ).reshape(-1, 3)
    return dirs


class Go2LidarRos2Node(Node):
    def __init__(self):
        super().__init__("go2_lidar_ros2")

        self.model = mujoco.MjModel.from_xml_path(GO2_SCENE)
        self.data = mujoco.MjData(self.model)

        self.pos = np.zeros(3, dtype=np.float64)
        self.quat = np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float64)  # w,x,y,z
        self.qj = np.zeros(12, dtype=np.float64)
        self.have_pos = False
        self.have_quat = False

        self._local_dirs = make_scan_directions()
        self._num_rays = self._local_dirs.shape[0]

        self.tf_broadcaster = TransformBroadcaster(self)
        self.points_pub = self.create_publisher(PointCloud2, "/points", 10)
        self.create_subscription(SportModeState, "/sportmodestate", self._on_sportmodestate, 10)
        self.create_subscription(LowState, "/lowstate", self._on_lowstate, 10)
        self.create_timer(1.0 / SCAN_RATE_HZ, self._scan_and_publish)
        self.get_logger().info(
            f"go2_lidar_ros2 ready. /points ({NUM_HORIZONTAL}h x {NUM_VERTICAL}v ="
            f" {self._num_rays} rays @ {SCAN_RATE_HZ}Hz, range<= {MAX_RANGE}m)"
            " + tf(world->lidar_link) を配信"
        )

    def _on_sportmodestate(self, msg: SportModeState):
        # unitree_mujocoはSportModeState.imu_state.quaternionを埋めない(常に0)ため、
        # 位置のみここから取り、姿勢は/lowstate.imu_state.quaternion(実測で値あり)を使う。
        self.pos[:] = msg.position
        self.have_pos = True

    def _on_lowstate(self, msg: LowState):
        self.quat[:] = msg.imu_state.quaternion  # [w, x, y, z]
        qj_dds = np.array([msg.motor_state[i].q for i in range(12)], dtype=np.float64)
        self.qj = qj_dds[IDX_DDS2MODEL]
        self.have_quat = True

    def _scan_and_publish(self):
        if not (self.have_pos and self.have_quat):
            return

        self.data.qpos[0:3] = self.pos
        self.data.qpos[3:7] = self.quat
        self.data.qpos[7:19] = self.qj
        mujoco.mj_forward(self.model, self.data)

        rotmat = quat_to_rotmat(*self.quat)
        origin = self.pos + rotmat @ MOUNT_OFFSET_BODY
        world_dirs = self._local_dirs @ rotmat.T

        geomid = np.zeros(1, dtype=np.int32)
        points = []
        for i in range(self._num_rays):
            dist = mujoco.mj_ray(
                self.model, self.data, origin, world_dirs[i], TERRAIN_GEOMGROUP, 1, -1, geomid
            )
            if 0.0 <= dist <= MAX_RANGE:
                # 点群は(実機ドライバの慣例通り)センサ座標系(lidar_link)で格納し、
                # world座標への変換はtf(world->lidar_link)側に任せる。
                points.append(dist * self._local_dirs[i])

        stamp = self.get_clock().now().to_msg()

        header = Header()
        header.stamp = stamp
        header.frame_id = "lidar_link"
        cloud = point_cloud2.create_cloud_xyz32(header, points)
        self.points_pub.publish(cloud)

        t = TransformStamped()
        t.header.stamp = stamp
        t.header.frame_id = "world"
        t.child_frame_id = "lidar_link"
        t.transform.translation.x = float(origin[0])
        t.transform.translation.y = float(origin[1])
        t.transform.translation.z = float(origin[2])
        t.transform.rotation.w = float(self.quat[0])
        t.transform.rotation.x = float(self.quat[1])
        t.transform.rotation.y = float(self.quat[2])
        t.transform.rotation.z = float(self.quat[3])
        self.tf_broadcaster.sendTransform(t)


def main():
    rclpy.init()
    node = Go2LidarRos2Node()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
