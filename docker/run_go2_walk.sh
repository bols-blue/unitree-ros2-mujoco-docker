#!/bin/bash
# go2_rl_gym の学習済みポリシーでGo2をMuJoCo上で歩かせる。
# ROS2/unitree_sdk2とは無関係の独立したPythonスクリプト (mujoco pip + torch のみ) なので、
# ROS2環境をsourceしたシェルから実行しても問題ない。
cd /opt/go2_rl_gym/deploy/deploy_mujoco
exec python3 deploy_go2.py "$@"
