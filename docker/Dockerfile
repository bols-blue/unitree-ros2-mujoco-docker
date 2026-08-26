FROM osrf/ros:humble-desktop

ENV DEBIAN_FRONTEND=noninteractive
SHELL ["/bin/bash", "-c"]

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential cmake git wget curl unzip ca-certificates \
        libyaml-cpp-dev libspdlog-dev libboost-all-dev libglfw3-dev \
        libeigen3-dev libfmt-dev \
        libgl1-mesa-dev libglu1-mesa mesa-utils \
        ros-humble-rmw-cyclonedds-cpp ros-humble-rosidl-generator-dds-idl \
        python3-colcon-common-extensions \
    && rm -rf /var/lib/apt/lists/*

# ---- unitree_sdk2 ----
RUN git clone --depth 1 https://github.com/unitreerobotics/unitree_sdk2.git /opt/src/unitree_sdk2 \
    && cmake -S /opt/src/unitree_sdk2 -B /opt/src/unitree_sdk2/build \
        -DCMAKE_INSTALL_PREFIX=/opt/unitree_robotics -DBUILD_EXAMPLES=OFF \
    && cmake --build /opt/src/unitree_sdk2/build -j"$(nproc)" \
    && cmake --install /opt/src/unitree_sdk2/build

# ---- MuJoCo (latest release binary distribution) ----
RUN MUJOCO_VER=$(curl -fsSL https://api.github.com/repos/google-deepmind/mujoco/releases/latest \
        | grep -m1 '"tag_name"' | sed -E 's/.*"tag_name":\s*"([^"]+)".*/\1/') \
    && echo "Installing MuJoCo ${MUJOCO_VER}" \
    && wget -q "https://github.com/google-deepmind/mujoco/releases/download/${MUJOCO_VER}/mujoco-${MUJOCO_VER}-linux-x86_64.tar.gz" -O /tmp/mujoco.tar.gz \
    && mkdir -p /opt/mujoco \
    && tar -xzf /tmp/mujoco.tar.gz -C /opt/mujoco --strip-components=1 \
    && rm /tmp/mujoco.tar.gz

# ---- unitree_mujoco simulator (C++, uses unitree_sdk2 + mujoco) ----
RUN git clone --depth 1 https://github.com/unitreerobotics/unitree_mujoco.git /opt/unitree_mujoco \
    && ln -s /opt/mujoco /opt/unitree_mujoco/simulate/mujoco \
    && cmake -S /opt/unitree_mujoco/simulate -B /opt/unitree_mujoco/simulate/build \
    && cmake --build /opt/unitree_mujoco/simulate/build -j"$(nproc)"

# ---- unitree_ros2 (Humble: apt cyclonedds is already the right version, only need to build the msg packages) ----
RUN git clone --depth 1 https://github.com/unitreerobotics/unitree_ros2.git /opt/unitree_ros2 \
    && source /opt/ros/humble/setup.bash \
    && cd /opt/unitree_ros2/cyclonedds_ws \
    && colcon build

# ---- unitree_mujoco's ROS2 sim-to-real example (stand_go2) ----
RUN source /opt/ros/humble/setup.bash \
    && source /opt/unitree_ros2/cyclonedds_ws/install/setup.bash \
    && cd /opt/unitree_mujoco/example/ros2 \
    && colcon build

# ---- unitree_ros2's own examples (low-level control: stand, single-joint move, state readback) ----
RUN source /opt/ros/humble/setup.bash \
    && source /opt/unitree_ros2/cyclonedds_ws/install/setup.bash \
    && cd /opt/unitree_ros2/example \
    && colcon build

# ---- raw unitree_sdk2 example (no ROS2 involved, talks DDS directly) ----
RUN cmake -S /opt/unitree_mujoco/example/cpp -B /opt/unitree_mujoco/example/cpp/build \
        -DCMAKE_BUILD_TYPE=Release \
    && cmake --build /opt/unitree_mujoco/example/cpp/build -j"$(nproc)"

# ---- RL locomotion policy for Go2 (go2_rl_gym, MIT-licensed community fork of unitree_rl_gym) ----
# unitree_rl_gym itself only ships pretrained sim2sim checkpoints for G1/H1/H1_2, not Go2.
# go2_rl_gym (https://github.com/wty-yy/go2_rl_gym) adds a trained Go2 policy + MuJoCo deploy script.
# Only the deploy_mujoco (inference) path is used here -- isaacgym/rsl_rl (training-only, GPU-only
# deps) are intentionally NOT installed, so no NVIDIA GPU is required to run this.
RUN apt-get update && apt-get install -y --no-install-recommends python3-pip \
    && rm -rf /var/lib/apt/lists/*

RUN pip3 install --no-cache-dir \
        torch --index-url https://download.pytorch.org/whl/cpu \
    && pip3 install --no-cache-dir \
        numpy pyyaml "mujoco==3.2.3" imageio imageio-ffmpeg pygame matplotlib

RUN git clone --depth 1 https://github.com/wty-yy/go2_rl_gym.git /opt/go2_rl_gym \
    # Default shipped config targets a stairs terrain, which this checkpoint destabilizes on
    # after a few seconds (verified). Default to flat ground for a stable walking demo.
    && sed -i 's#resources/robots/go2/cross_stairs.xml#resources/robots/go2/flat.xml#' \
        /opt/go2_rl_gym/deploy/deploy_mujoco/configs/go2.yaml
ENV PYTHONPATH="/opt/go2_rl_gym:${PYTHONPATH}"

# rclpy (already in ros-humble-desktop) needs the same torch/numpy/yaml installed above
# to run the go2_rl_gym policy as a ROS2 node bridging /lowstate <-> /lowcmd.
COPY go2_walk_ros2_node.py /opt/go2_walk_ros2_node.py

COPY setup_env.sh /opt/setup_env.sh
COPY run_mujoco.sh /opt/run_mujoco.sh
COPY run_go2_walk.sh /opt/run_go2_walk.sh
COPY run_go2_walk_ros2.sh /opt/run_go2_walk_ros2.sh
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /opt/setup_env.sh /opt/run_mujoco.sh /opt/run_go2_walk.sh /opt/run_go2_walk_ros2.sh /entrypoint.sh

WORKDIR /root
ENTRYPOINT ["/entrypoint.sh"]
CMD ["bash"]
