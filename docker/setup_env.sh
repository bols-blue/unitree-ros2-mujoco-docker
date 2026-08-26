#!/bin/bash
# Unitree ROS2 (rclcpp/ros2 CLI等) 用の環境設定
# 実機には接続しない前提でループバック(lo)インターフェースを使用する
#
# 注意: このスクリプトは ROS2 コマンドを使う端末でのみ source すること。
# /opt/unitree_mujoco/simulate/build/unitree_mujoco (MuJoCo本体) を動かす端末では
# 絶対に source しないこと。ROS2側のcyclonedds共有ライブラリ(/opt/ros/humble/lib)が
# unitree_sdk2が同梱するcyclonedds(/opt/unitree_robotics/lib)より優先されてしまい、
# 2つのバージョン違いのlibddsc.so/libddscxx.soが混在してDDSアサーションエラーで
# クラッシュする(unitreerobotics/unitree_mujoco issue #60)。
# MuJoCo本体は run_mujoco.sh 経由で、ROS2を一切sourceしていない端末から起動すること。

source /opt/ros/humble/setup.bash
source /opt/unitree_ros2/cyclonedds_ws/install/setup.bash
if [ -f /opt/unitree_mujoco/example/ros2/install/setup.bash ]; then
    source /opt/unitree_mujoco/example/ros2/install/setup.bash
fi

export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
export CYCLONEDDS_URI='<CycloneDDS><Domain><General><Interfaces>
                            <NetworkInterface name="lo" priority="default" multicast="default" />
                        </Interfaces></General></Domain></CycloneDDS>'
# unitree_mujoco/simulate/config.yaml のデフォルト domain_id と合わせる
export ROS_DOMAIN_ID=1
