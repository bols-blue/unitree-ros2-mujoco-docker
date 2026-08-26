#!/bin/bash
# MuJoCoシミュレータ本体を、ROS2環境を一切sourceしていないクリーンな状態で起動する。
# ROS2のcyclonedds共有ライブラリと衝突させないため、直接execする。
cd /opt/unitree_mujoco/simulate/build
exec ./unitree_mujoco "$@"
