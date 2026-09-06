# Go2 操作卓コンテナ(ドメイン30)

`../docker/`のGo2シミュレータ(ドメイン1)から独立した、`teleop_twist_keyboard`・`rviz2`専用の
操作卓コンテナです。単独では動きません。`../docker/`側のシミュレータ・domain_bridgeと組み合わせて
使う前提のドキュメントです。

## ドメインを分離した運用(ロボット側=ドメイン1、操作卓側=ドメイン30、動作確認済み)

シミュレータ側は`../docker/`の他の節と同じデフォルトドメイン(1)のまま動かし、`teleop_twist_keyboard`・
`rviz2`だけを隔離された別ドメイン(30)・別コンテナ(このディレクトリ)で動かす構成です。両ドメイン間は
[`ros-humble-domain-bridge`](https://github.com/ros-tooling/domain_bridge)(`../docker/domain_bridge.yaml`)で
中継し、**`/points`・`/tf`(1→30)・`/cmd_vel`(30→1)の3トピックだけ**が橋渡しされます。
`/lowstate`・`/lowcmd`・`/sportmodestate`等のロボット内部トピックはドメイン30には一切漏れません。

```
Domain 1 (../docker/, シミュレータコンテナ)            Domain 30 (このコンテナ)
  unitree_mujoco                                        teleop_twist_keyboard
  go2_walk_ros2_node.py (RL歩行)      domain_bridge         │ /cmd_vel
  go2_lidar_ros2_node.py (疑似3D LiDAR) ⇄  /points ────────▶ rviz2
                                          ⇄  /tf ──────────▶ rviz2
                                          ⇄  /cmd_vel ◀──── teleop_twist_keyboard
```

両コンテナとも`network_mode: host`なので実質ホストのネットワーク名前空間を共有しており、
loopback(`lo`)経由のDDS通信はコンテナをまたいでもそのまま届きます。

### 起動手順(ドメイン1側、`../docker/`コンテナ・4ターミナル)

事前準備(初回のみ、リポジトリルートで実行):

```bash
cd docker
docker compose build
```

```bash
# ターミナル1: MuJoCo本体を起動するコンテナに入る(ROS2はsourceしない)
xhost +local:docker   # 初回のみ
cd docker
docker compose run --rm unitree-sim
```
```bash
# ターミナル1(続き): コンテナに入った直後のシェルでそのまま実行
/opt/run_mujoco.sh -r go2 -s scene_terrain.xml
```
```bash
# ターミナル2: RL歩行ポリシー(/cmd_vel購読)。同じコンテナにもう1つシェルで入る
docker exec -it unitree-ros2-sim bash
```
```bash
# ターミナル2(続き)
/opt/run_go2_walk_ros2.sh
```
```bash
# ターミナル3: 疑似3D LiDARブリッジ。同じコンテナにもう1つシェルで入る
docker exec -it unitree-ros2-sim bash
```
```bash
# ターミナル3(続き)
/opt/run_go2_lidar_ros2.sh
```
```bash
# ターミナル4: domain_bridge(ドメイン1 <-> 30)。同じコンテナにもう1つシェルで入る
docker exec -it unitree-ros2-sim bash
```
```bash
# ターミナル4(続き)
/opt/run_domain_bridge.sh
```

### 起動手順(ドメイン30側、このコンテナ・2ターミナル)

事前準備(初回のみ、リポジトリルートで実行):

```bash
cd docker_operator
docker compose build
```

```bash
# ターミナル5: teleop。操作卓コンテナを起動してこのシェルに入る
xhost +local:docker   # 初回のみ(ドメイン1側で既に実行済みなら不要)
cd docker_operator
docker compose run --rm operator
```
```bash
# ターミナル5(続き): コンテナに入った直後のシェルでそのまま実行
source /opt/setup_env_domain30.sh
ros2 run teleop_twist_keyboard teleop_twist_keyboard
```
```bash
# ターミナル6: rviz2。同じコンテナにもう1つシェルで入る
docker exec -it unitree-ros2-operator bash
```
```bash
# ターミナル6(続き)
source /opt/setup_env_domain30.sh
rviz2
```
rviz2で「Fixed Frame」を`world`に設定し、「Add」→ **PointCloud2**(Topic: `/points`)と **TF** を追加すれば、
teleopのキー操作でGo2が歩き、その3D LiDAR点群がドメインをまたいで表示されます。

### 終了する場合

- ターミナル1(`docker compose run --rm unitree-sim`で起動したシェル)を`exit`または`Ctrl-D`で抜けると、
  `--rm`によりコンテナごと自動的に削除されます(ターミナル2〜4の`docker exec`シェルも道連れで終了します)。
- 同様にターミナル5(`docker compose run --rm operator`)を抜けると操作卓コンテナも削除されます。
