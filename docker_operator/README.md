# Go2 操作卓コンテナ(ドメイン30)

`../docker/`のGo2シミュレータ(ドメイン1)から独立した、`domain_bridge`・`teleop_twist_keyboard`・`rviz2`
専用の操作卓コンテナです。単独では動きません。`../docker/`側のシミュレータと組み合わせて使う前提の
ドキュメントです。

## ドメインを分離した運用(ロボット側=ドメイン1、操作卓側=ドメイン30、動作確認済み)

シミュレータ側は`../docker/`の他の節と同じデフォルトドメイン(1)のまま動かし、`domain_bridge`・
`teleop_twist_keyboard`・`rviz2`はすべて隔離された別ドメイン(30)・別コンテナ(このディレクトリ)で
動かす構成です。両ドメイン間は[`ros-humble-domain-bridge`](https://github.com/ros-tooling/domain_bridge)
(`domain_bridge.yaml`)で中継し、**`/points`・`/tf`(1→30)・`/cmd_vel`(30→1)の3トピックだけ**が
橋渡しされます。`/lowstate`・`/lowcmd`・`/sportmodestate`等のロボット内部トピックはドメイン30には
一切漏れません。

```
Domain 1 (../docker/, シミュレータコンテナ)            Domain 30 (このコンテナ)
  unitree_mujoco                                        domain_bridge
  go2_walk_ros2_node.py (RL歩行)          /cmd_vel ◀───────┤ teleop_twist_keyboard
  go2_lidar_ros2_node.py (疑似3D LiDAR) ──▶ /points ────────┤
                                        ──▶ /tf ────────────┤
                                                             └─▶ rviz2
```

両コンテナとも`network_mode: host`なので実質ホストのネットワーク名前空間を共有しており、
loopback(`lo`)経由のDDS通信はコンテナをまたいでもそのまま届きます。domain_bridgeはYAML内で
ドメインIDを個別指定するため、どちらのコンテナで動かしても機能は同じですが、
「ロボット側の内部トピックを一切ドメイン30に持ち込まない」構成の意図を明確にするため、
このコンテナ(ドメイン30側)で動かしています。

### 起動手順(ドメイン1側、`../docker/`コンテナ・3ターミナル)

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

### 起動手順(ドメイン30側、このコンテナ・3ターミナル)

事前準備(初回のみ、リポジトリルートで実行):

```bash
cd docker_operator
docker compose build
```

```bash
# ターミナル4: domain_bridge。操作卓コンテナを起動してこのシェルに入る
xhost +local:docker   # 初回のみ(ドメイン1側で既に実行済みなら不要)
cd docker_operator
docker compose run --rm operator
```
```bash
# ターミナル4(続き): コンテナに入った直後のシェルでそのまま実行
/opt/run_domain_bridge.sh
```
```bash
# ターミナル5: teleop。同じコンテナにもう1つシェルで入る
docker exec -it unitree-ros2-operator bash
```
```bash
# ターミナル5(続き)
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

### 終了する場合

- ターミナル1(`docker compose run --rm unitree-sim`で起動したシェル)を`exit`または`Ctrl-D`で抜けると、
  `--rm`によりコンテナごと自動的に削除されます(ターミナル2〜3の`docker exec`シェルも道連れで終了します)。
- 同様にターミナル4(`docker compose run --rm operator`)を抜けると操作卓コンテナも削除されます
  (ターミナル5〜6も道連れ)。

## rviz2の使い方

### 1. 起動とFixed Frameの設定

`rviz2`を起動すると空のウィンドウが開きます。まず左上の「Displays」パネルにある
**Global Options → Fixed Frame** を`world`に変更してください(デフォルトは`map`になっており、
`map`フレームは存在しないため何も表示されません)。

### 2. 表示(Display)の追加

左下の **Add** ボタンをクリックし、「By topic」タブから追加すると型を自動判別してくれるので簡単です。

- **TF**: ロボットの姿勢(`world`→`lidar_link`)が座標軸として表示されます
- **PointCloud2**(Topic: `/points`): LiDARの3D点群が表示されます

「By display type」タブから手動で選んで後からTopicを指定することもできます。

### 3. 見やすくする設定

**PointCloud2**を選択した状態で右側のプロパティから:

- `Size (Pixels)`: 2〜4程度に上げると点が見やすくなります
- `Color Transformer`: `AxisColor`にすると高さ(Z)で色分けされ、地形の起伏が分かりやすくなります
- `Decay Time`: 0だと最新フレームのみ表示、大きくすると軌跡のように点が残ります

### 4. 視点操作(マウス)

- **左ドラッグ**: 視点を回転(オービット)
- **右ドラッグ or ホイールドラッグ**: パン(平行移動)
- **スクロール**: ズーム

teleopでロボットが動くと、TF・点群もそれに追従して自動更新されます。

### 5. 設定の保存

`File → Save Config As...`で設定(Fixed Frame・追加したDisplay・プロパティ)を`.rviz`ファイルに
保存できます。次回`rviz2 -d 保存したファイル.rviz`で起動すれば、毎回Add操作をやり直す必要が
なくなります。
