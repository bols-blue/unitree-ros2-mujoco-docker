#!/bin/bash
set -e
# ROS2は自動でsourceしない。MuJoCo本体とROS2ノードはcyclonedds実装の
# バージョンが衝突するため別プロセス/別シェルで扱う (詳細はREADME.md参照)。
cat <<'EOF'
==========================================================================
 Unitree ROS2 + MuJoCo シミュレーション環境

 [MuJoCoシミュレータを起動する場合] (ROS2はsourceしない)
   /opt/run_mujoco.sh -r go2 -s scene_terrain.xml

 [ROS2コマンド/ノードを使う場合] (別のシェル: docker exec -it ... bash)
   source /opt/setup_env.sh
   ros2 topic list
   /opt/unitree_mujoco/example/ros2/install/stand_go2/bin/stand_go2
==========================================================================
EOF
exec "$@"
