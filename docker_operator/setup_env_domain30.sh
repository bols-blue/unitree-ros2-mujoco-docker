#!/bin/bash
# オペレータ側(teleop_twist_keyboard・rviz2)用のROS2環境設定。
# docker/setup_env.shと同じくloopback(lo)インターフェース・cyclonedds実装を使うが、
# ドメインIDは30(操作卓側)。docker/側のドメイン1とはdomain_bridge経由でのみつながる。
source /opt/ros/humble/setup.bash

export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
export CYCLONEDDS_URI='<CycloneDDS><Domain><General><Interfaces>
                            <NetworkInterface name="lo" priority="default" multicast="default" />
                        </Interfaces></General></Domain></CycloneDDS>'
export ROS_DOMAIN_ID=30
