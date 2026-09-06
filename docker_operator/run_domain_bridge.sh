#!/bin/bash
# Go2シミュレータ(ドメイン1、../docker/コンテナ)とオペレータ側(ドメイン30、このコンテナ)の間で
# /points・/tf・/cmd_vel の3トピックだけを中継する domain_bridge を起動する。
# domain_bridge自体はYAML内でドメインIDを個別指定するため、このシェルのROS_DOMAIN_IDは
# 使われない(setup_env_domain30.shの再sourceはCycloneDDSのインターフェース設定を得るためだけに行う)。
source /opt/setup_env_domain30.sh
exec ros2 run domain_bridge domain_bridge /opt/domain_bridge.yaml "$@"
