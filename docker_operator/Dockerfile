FROM osrf/ros:humble-desktop

ENV DEBIAN_FRONTEND=noninteractive
SHELL ["/bin/bash", "-c"]

# ドメイン1側(docker/)と同じRMW実装(cyclonedds)に揃えることで、
# domain_bridge越しの相互運用まわりの余計な差異を避ける。
RUN apt-get update && apt-get install -y --no-install-recommends \
        ros-humble-rmw-cyclonedds-cpp \
        ros-humble-teleop-twist-keyboard \
    && rm -rf /var/lib/apt/lists/*

COPY setup_env_domain30.sh /opt/setup_env_domain30.sh
RUN chmod +x /opt/setup_env_domain30.sh

WORKDIR /root
CMD ["bash"]
