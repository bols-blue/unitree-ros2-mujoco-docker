#!/bin/bash
# go2_rl_gymの学習済み歩行ポリシーを、ROS2トピック(/lowstate, /lowcmd)経由でGo2に適用する。
# 事前に別シェルで /opt/run_mujoco.sh -r go2 -s scene_terrain.xml を起動しておくこと。
#
# ROS_DISTRO はベースイメージが常にセットしている環境変数なので、
# 「setup_env.sh をsource済みか」の判定には使えない(rclpyがimportできないだけの
# 状態でも ROS_DISTRO=humble のまま)。source済みかに関わらず毎回sourceする
# (setup_env.shの再sourceは安全・冪等)。
source /opt/setup_env.sh
exec python3 /opt/go2_walk_ros2_node.py "$@"
