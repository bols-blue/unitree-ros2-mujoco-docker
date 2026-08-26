# Unitree ROS2 + MuJoCo シミュレーション環境（Docker）

`unitree_ros2`（ROS2 Humble） + `unitree_mujoco`（公式MuJoCoシミュレータ）をひとつのコンテナにまとめた環境です。
実機には接続せず、ループバック(`lo`)インターフェース + DDSドメインID `1` でシミュレーションのみ動作します。

## 前提

- Linuxホスト（GUI表示のためX11が使えること）
- Docker / Docker Compose
- GPUなしでもOK（`LIBGL_ALWAYS_SOFTWARE=1` によりソフトウェアレンダリングで動作）

## ビルド

```bash
cd docker
docker compose build
```

初回は ROS2 Humble desktopイメージのダウンロード、unitree_sdk2・MuJoCo・unitree_ros2のビルドが走るため時間がかかります（数分〜十数分程度）。

## 起動

ホスト側でコンテナからのX11接続を許可してから起動します。

```bash
xhost +local:docker
cd docker
docker compose run --rm unitree-sim
```

**重要**: MuJoCo本体とROS2は、必ず別々のシェルで扱ってください。同じシェルでROS2環境(`setup_env.sh`)をsourceした状態で `unitree_mujoco` を起動すると、ROS2側のcyclonedds共有ライブラリ(`/opt/ros/humble/lib`)が
unitree_sdk2同梱のcyclonedds(`/opt/unitree_robotics/lib`)より優先されて読み込まれ、バージョン違いの
`libddsc.so` / `libddscxx.so` が混在してDDSのアサーションエラーでクラッシュします
（[unitreerobotics/unitree_mujoco issue #60](https://github.com/unitreerobotics/unitree_mujoco/issues/60)）。
そのためコンテナ起動時はROS2を自動sourceしない構成にしています。

## 動作確認

### 1. MuJoCoシミュレータを起動（ターミナル1、ROS2はsourceしない）

```bash
/opt/run_mujoco.sh -r go2 -s scene_terrain.xml
```

Go2ロボットが読み込まれたMuJoCoウィンドウが表示されれば成功です。

### 2. 別ターミナルからROS2で状態を確認（ターミナル2）

同じコンテナにもう1つ入る:

```bash
docker exec -it unitree-ros2-sim bash
source /opt/setup_env.sh
```

```bash
ros2 topic list
ros2 topic echo /lowstate
```

### 3. サンプルプログラムでロボットを立たせる

同じくROS2をsource済みのターミナルで:

```bash
source /opt/setup_env.sh   # 未sourceなら
/opt/unitree_mujoco/example/ros2/install/stand_go2/bin/stand_go2
```

Enterキーを押すと制御が開始され、MuJoCo上のGo2が起立します。ROS2 ↔ MuJoCo シミュレータ間のDDS通信が正しく動作している証拠です。

## ロボットの動かし方

`unitree_mujoco` がブリッジしているのは **低レベル制御（`/lowcmd`で各モーターのq/dq/tauを直接指定するPD制御）** と状態読み取り（`/lowstate`, `/sportmodestate`, `/wirelesscontroller`）だけです。
実機のオンボードファームウェアが提供する「歩く／旋回する」といった**高レベルSport API（`/api/sport/request`、`SportClient`）はこのシミュレータでは実装されていません**（`go2_sport_client`等を実行しても、シミュレータ側に受信するノードが無いため無反応です）。実機専用と考えてください。

### 1. 起立させる（動作確認済み）

ターミナル1（ROS2はsourceしない）:
```bash
/opt/run_mujoco.sh -r go2 -s scene_terrain.xml
```

ターミナル2:
```bash
source /opt/setup_env.sh
cd /opt/unitree_ros2/example
./install/unitree_ros2_example/bin/go2_stand_example lo
```
4脚の関節が座り姿勢から立ち姿勢へ動きます（`/lowstate`の`motor_state[].q`が変化することを確認済み）。

`/opt/unitree_mujoco/example/ros2/install/stand_go2/bin/stand_go2` も同様の起立デモです（Enterキー入力が必要）。

### 2. 特定の関節だけ動かす

```bash
source /opt/setup_env.sh
cd /opt/unitree_ros2/example
./install/unitree_ros2_example/bin/low_level_ctrl
```
RL脚（後左脚）のhipとcalfモーターが指定角度まで回転します。ソース(`example/src/src/low_level_ctrl.cpp`)を見れば、他の関節・角度に変更する方法が分かります。

### 3. 実際に歩かせる（強化学習ポリシー、動作確認済み）

`unitree_ros2`/`unitree_mujoco`自体には歩行ジェネレータ（歩容生成アルゴリズム）が含まれていないため、「歩く」動作をさせるには自分で歩行アルゴリズムを実装するか、学習済みの強化学習（RL）ポリシーを使う必要があります。

Unitree公式の[`unitree_rl_gym`](https://github.com/unitreerobotics/unitree_rl_gym)は**G1/H1/H1_2用の学習済みチェックポイントは配布していますが、Go2用はありません**（Go2は学習環境とURDFのみ提供、チェックポイントは無し）。そのためGPUで一から学習する必要がありますが、このホストにはNVIDIA GPUが無く、Isaac Gymでの学習は非現実的です。

代わりに、`unitree_rl_gym`と同じ枠組みでGo2の学習済みポリシーを含むMITライセンスのコミュニティフォーク [`go2_rl_gym`](https://github.com/wty-yy/go2_rl_gym)（RSS 2026関連実装）を組み込みました。**推論のみ（学習はしない）なのでGPU不要、CPUで実時間より速く動作します。** ROS2/unitree_sdk2やDDSとは無関係の独立したPython実装（`mujoco`のpipパッケージ + `torch` CPU版）なので、前述のcyclonedds衝突問題とも無関係です。

```bash
/opt/run_go2_walk.sh
```

平地(`flat.xml`)で前進コマンド（`cmd_init: [1.0, 0.0, 0.0]` = 前進1.0m/s）を与えた状態でMuJoCoビューアが起動し、Go2が実際に歩き出します。検証済みの実測結果（GUI無し・10秒間のヘッドレス実行）:

| 時刻 | 位置 x,y,z (m) | 姿勢(quat_w) |
|---|---|---|
| 1s | +0.61, -0.02, 0.34 | 1.00 |
| 5s | +4.36, +0.00, 0.35 | 1.00 |
| 10s | +9.04, +0.16, 0.34 | 1.00 |

10秒でx方向に約9m前進（≒0.9m/s、指令値1.0m/sとほぼ一致）、高さ・姿勢とも安定したまま歩行を継続することを確認済みです。

Xboxコントローラーを接続していれば、左スティックで前後左右、右スティックで旋回のコマンドを与えられます（未接続時は`configs/go2.yaml`の`cmd_init`が使われ続けます）。動画を保存したい場合は:
```bash
/opt/run_go2_walk.sh --save-video   # /opt/go2_rl_gym/deploy/deploy_mujoco/videos/ に保存
```

他の地形（階段・坂道）を試したい場合は`/opt/go2_rl_gym/deploy/deploy_mujoco/configs/go2.yaml`の`xml_path`をコメントアウトされた候補に切り替えられますが、**`cross_stairs.xml`はこの学習済みポリシーだと数秒で不安定化して転倒することを確認済み**なので、デフォルトは`flat.xml`にしています。

### 3b. 同じポリシーをROS2経由(`/lowstate`→`/lowcmd`)で動かす（動作確認済み）

上記`run_go2_walk.sh`はmujocoのPythonバインディングで物理演算そのものを自分のプロセス内で行っており、ROS2/DDSを一切使っていません。**ROS2ツール（`ros2 topic`, rosbag, rviz等）から見える形で歩かせたい場合**は、`/opt/run_mujoco.sh`で起動しているC++版`unitree_mujoco`シミュレータに対し、ROS2ノードとして`/lowstate`を読んで`/lowcmd`を書く方式（`go2_walk_ros2_node.py`）を用意しました。同じ学習済みポリシー(`go2_moe_cts_high_slope_thre_164k_0.6715.pt`)を使いますが、こちらは正真正銘のROS2ノードです。

```bash
# ターミナル1（ROS2はsourceしない）
/opt/run_mujoco.sh -r go2 -s scene_terrain.xml
```
```bash
# ターミナル2
docker exec -it unitree-ros2-sim bash
/opt/run_go2_walk_ros2.sh
```

実測結果（`/sportmodestate`のpositionを1.2秒おとに取得）:

| 時刻 | 位置 x,y,z (m) |
|---|---|
| 0s | +0.67, +0.19, 0.37 |
| 3.6s | +1.06, +0.57, 0.50 |
| 6.0s | +4.68, +1.17, 0.40 |
| 8.4s | +9.02, +1.93, 0.40 |

前進・起立は安定して継続しますが、`run_go2_walk.sh`（プロセス内物理演算、y方向ドリフトはほぼ0）と比べると、**DDSの往復レイテンシの影響でわずかに左に弧を描くように歩く**ことを確認しています（8.4秒でx+9m進む間にyが+1.9m）。転倒はしないため実用上は問題ありませんが、より直進性を求める場合は`cmd`に微小な旋回補正（`cmd_init`の3要素目、yaw方向）を加えるなどの調整余地があります。

実装上のポイント（`docker/go2_walk_ros2_node.py`）:
- `/lowstate`のIMU（`quaternion`, `gyroscope`）とモーター角度/角速度から観測ベクトルを再構成し、独立したタイマーではなく**`/lowstate`受信コールバック内で直接時間を見て間引く**ことで遅延を最小化しています（独立タイマー方式では位相ズレで歩行が不安定化することを確認済み）。
- `unitree_go`のLowCmd/LowState内のモーター配列順は`FR,FL,RR,RL`（`unitree_ros2/example`の`motor_crc.h`で定義される`FR_0=0, FL_0=3, RR_0=6, RL_0=9`と一致）で、go2_rl_gymのポリシーが期待する関節順（`FL,FR,RL,RR`）とは異なるため、`go2.yaml`の`model_joint_names`を使って両者を関節名ベースで相互変換しています。

### 3c. `teleop_twist_keyboard`でキーボード操作する（動作確認済み）

`go2_walk_ros2_node.py`は`/cmd_vel`(`geometry_msgs/msg/Twist`)を購読しており、`linear.x`/`linear.y`/`angular.z`を`go2.yaml`の`max_cmd`（前後・左右・旋回の速度上限）でクリップして即座に歩行コマンドへ反映します。`ros-humble-teleop-twist-keyboard`はイメージに標準搭載済みです。

```bash
# ターミナル1（ROS2はsourceしない）
/opt/run_mujoco.sh -r go2 -s scene_terrain.xml
```
```bash
# ターミナル2: 歩行ブリッジノード
docker exec -it unitree-ros2-sim bash
/opt/run_go2_walk_ros2.sh
```
```bash
# ターミナル3: キーボード操作
docker exec -it unitree-ros2-sim bash
source /opt/setup_env.sh
ros2 run teleop_twist_keyboard teleop_twist_keyboard
```
`i`で前進、`,`で後退、`j`/`l`で旋回、`k`で停止、といった通常のteleop_twist_keyboard操作でGo2の歩行方向・速度をリアルタイムに変えられます。`/cmd_vel`に`{0,0,0}`（`k`キーまたは無操作）を送るとその場で安定して立ち止まることを実測確認済みです。

**注意**: `teleop_twist_keyboard`のデフォルト速度(0.5m/s前後、旋回1.0rad/s)は`go2.yaml`の`max_cmd: [2.0, 1.0, 2.5]`の範囲内なのでそのまま使えますが、速度を上げすぎる（`q`/`z`キーで倍率変更）とこの学習済みポリシーの想定範囲を超えて不安定化する可能性があります。

## unitree_sdk2を直接使う（ROS2を介さないC++）

ROS2を経由せず、Unitreeの生のC++ SDK（`unitree_sdk2`）でDDS通信を直接書きたい場合の使い方です。
`unitree_sdk2`はイメージビルド時に`/opt/unitree_robotics`へインストール済みなので、追加セットアップは不要です。

### 動作確認済みのサンプル

```bash
docker exec -it unitree-ros2-sim bash
/opt/unitree_mujoco/example/cpp/build/stand_go2
```
（ターミナル1で`/opt/run_mujoco.sh -r go2 -s scene_terrain.xml`が起動している状態で）Enterを押すと、ROS2を一切経由せず直接DDSでGo2を起立させます。ROS2側の`ros2 topic echo /lowstate`でも同じDDSバス上のデータが見えることを確認済みです。

**重要: シミュレーション時は引数なしで実行してください。** ソース(`stand_go2.cpp`)を見ると、

```cpp
if (argc < 2)
    ChannelFactory::Instance()->Init(1, "lo");   // 引数なし → シミュレーション用 (domain 1, lo)
else
    ChannelFactory::Instance()->Init(0, argv[1]); // 引数あり → 実機用 (domain 0, 指定NIC)
```
という切り替えになっているため、`./stand_go2 lo`のように引数を渡すと実機用のdomain 0で初期化されてしまい、MuJoCo（domain 1）と通信できません。この規約は`unitree_ros2`/`unitree_sdk2`系のサンプルで概ね共通です。

### 自分のプログラムを書く場合

`/opt/unitree_mujoco/example/cpp/`（`stand_go2.cpp` + `CMakeLists.txt`）がそのままテンプレートになります。最小構成のCMakeLists.txtは:

```cmake
cmake_minimum_required(VERSION 3.16)
project(my_app)
list(APPEND CMAKE_PREFIX_PATH "/opt/unitree_robotics/lib/cmake")
find_package(unitree_sdk2 REQUIRED)
add_executable(my_app main.cpp)
target_link_libraries(my_app unitree_sdk2)
```

C++コード側では`unitree/robot/channel/channel_factory.hpp`等をincludeし、`ChannelFactory::Instance()->Init(1, "lo")`でシミュレーション用に初期化してから、`unitree_go::msg::dds_::LowCmd_`等のDDSメッセージをpublish/subscribeします。詳細は`stand_go2.cpp`と[unitree_sdk2のドキュメント](https://github.com/unitreerobotics/unitree_sdk2)を参照してください。

### Python SDK (unitree_sdk2_python) について

このイメージにはデフォルトでは入れていません。Pythonで直接SDKを叩きたい場合は追加が必要です（`pip install cyclonedds`系の依存関係があり、`unitree_ros2`のC++側cyclonedds設定と衝突しないか確認が必要になるため、別途対応します）。必要であれば教えてください。

## 実機に接続する場合

このコンテナはシミュレーション専用設定（`lo` インターフェース、`ROS_DOMAIN_ID=1`）です。
実機を使う場合は `docker-compose.yml` に `network_mode: host` は既に設定済みなので、コンテナ内で
`/opt/unitree_ros2/setup.sh` を参考に `CYCLONEDDS_URI` のインターフェース名を実機と接続するNIC名（例: `enp3s0`）に変更し、
`ROS_DOMAIN_ID=0` に戻して使用してください。

## 既知の制約・デメリット

- MuJoCo本体とROS2ノードは、cyclonedds実装のバージョン衝突を避けるため必ず別シェルで実行する必要があります（上記参照）。
- `network_mode: host` を使うため、Docker Desktop（Windows/Mac）環境ではDDSのマルチキャストがうまく機能しません。Linuxホストでの利用を前提としています。
- GPUなしのためMuJoCoの描画はソフトウェアレンダリング（llvmpipe）になり、ネイティブ実行より重くなります。GPUがある場合は `nvidia-container-toolkit` を導入し、`LIBGL_ALWAYS_SOFTWARE=1` を外してNVIDIAランタイムを使う方が高速です。
- 低レベル制御のリアルタイム性を厳密に検証したい場合は、コンテナのオーバーヘッドが無視できないことがあります。
