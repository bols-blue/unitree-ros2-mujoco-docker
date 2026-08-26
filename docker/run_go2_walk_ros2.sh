#!/bin/bash
# go2_rl_gymの学習済み歩行ポリシーを、ROS2トピック(/lowstate, /lowcmd)経由でGo2に適用する。
# 事前に別シェルで /opt/run_mujoco.sh -r go2 -s scene_terrain.xml を起動しておくこと。
# ROS2をsourceしていない場合は自動でsourceする。
if [ -z "$ROS_DISTRO" ]; then
    source /opt/setup_env.sh
fi
exec python3 /opt/go2_walk_ros2_node.py "$@"
