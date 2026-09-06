#!/bin/bash
# Go2シミュレータ(ドメイン1)とオペレータ側(ドメイン30、docker_operator/コンテナ)の間で
# /points・/tf・/cmd_vel の3トピックだけを中継する domain_bridge を起動する。
# domain_bridge自体はYAML内でドメインIDを個別指定するため、このシェルのROS_DOMAIN_IDは
# 使われない(setup_env.shの再sourceはCycloneDDSのインターフェース設定を得るためだけに行う)。
source /opt/setup_env.sh
exec ros2 run domain_bridge domain_bridge /opt/domain_bridge.yaml "$@"
