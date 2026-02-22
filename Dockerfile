# Unitree MuJoCo + RL-MJLab G1 deploy controller (DDS) image
FROM ubuntu:22.04

ARG DEBIAN_FRONTEND=noninteractive
ARG MUJOCO_VERSION=3.3.0
ARG CYCLONEDDS_VERSION=0.10.2
ARG CYCLONEDDS_CXX_VERSION=0.10.2

SHELL ["/bin/bash", "-c"]

# Base system and build dependencies.
RUN apt-get update && apt-get install --no-install-recommends -y \
    build-essential \
    cmake \
    git \
    vim \
    wget \
    curl \
    ca-certificates \
    tzdata \
    pkg-config \
    python3-pip \
    python3-dev \
    python3-venv \
    libosmesa6-dev \
    libgl1-mesa-dev \
    libglfw3-dev \
    libglew-dev \
    libx11-dev \
    libxrandr-dev \
    libxcursor-dev \
    libxinerama-dev \
    libxi-dev \
    libsm6 \
    libice6 \
    libwayland-dev \
    libxcb1 \
    libosmesa6 \
    libglvnd-dev \
    libglvnd0 \
    libgl1 \
    libxext6 \
    libxxf86vm1 \
    xvfb \
    ffmpeg \
    libyaml-cpp-dev \
    libboost-all-dev \
    libeigen3-dev \
    libspdlog-dev \
    libfmt-dev \
    zlib1g-dev \
    openssl \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

# Install MuJoCo.
ARG MUJOCO_TARBALL=mujoco-${MUJOCO_VERSION}-linux-x86_64.tar.gz
ARG MUJOCO_URL=https://github.com/google-deepmind/mujoco/releases/download/${MUJOCO_VERSION}/${MUJOCO_TARBALL}
RUN mkdir -p /opt && \
    curl -fsSL "${MUJOCO_URL}" -o /tmp/mujoco.tar.gz && \
    tar -xzf /tmp/mujoco.tar.gz -C /opt && \
    mv /opt/mujoco-${MUJOCO_VERSION} /opt/mujoco && \
    rm -f /tmp/mujoco.tar.gz && \
    chmod +x /opt/mujoco/bin/simulate

# Python deps for simulator + YAML patching in launcher script.
RUN python3 -m pip install --no-cache-dir --upgrade pip setuptools wheel && \
    python3 -m pip install --no-cache-dir \
      mujoco==${MUJOCO_VERSION} \
      pygame \
      pyyaml \
      numpy \
      scipy \
      yourdfpy \
      opencv-python \
      noise \
      cython

ENV MUJOCO_HOME=/opt/mujoco
ENV MUJOCO_MODEL_DEFAULT=/opt/mujoco/model/humanoid/humanoid.xml
ENV LD_LIBRARY_PATH=/opt/mujoco/bin:/usr/local/lib:/usr/lib
ENV PATH=/opt/mujoco/bin:${PATH}

# Build CycloneDDS core from source to match Unitree SDK expectations.
RUN set -e; \
    git clone --branch "${CYCLONEDDS_VERSION}" --depth 1 https://github.com/eclipse-cyclonedds/cyclonedds.git /tmp/cyclonedds; \
    cmake -S /tmp/cyclonedds -B /tmp/cyclonedds/build \
      -DCMAKE_BUILD_TYPE=Release \
      -DBUILD_EXAMPLES=OFF \
      -DBUILD_IDLC=ON \
      -DENABLE_SSL=NO; \
    cmake --build /tmp/cyclonedds/build -j"$(nproc)"; \
    cmake --install /tmp/cyclonedds/build; \
    ldconfig; \
    rm -rf /tmp/cyclonedds

# Build CycloneDDS C++ bindings from source (required by unitree_sdk2 / g1_ctrl link).
RUN set -e; \
    git clone --branch "${CYCLONEDDS_CXX_VERSION}" --depth 1 https://github.com/eclipse-cyclonedds/cyclonedds-cxx.git /tmp/cyclonedds-cxx; \
    cmake -S /tmp/cyclonedds-cxx -B /tmp/cyclonedds-cxx/build \
      -DCMAKE_BUILD_TYPE=Release \
      -DCycloneDDS_DIR=/usr/local/lib/cmake/CycloneDDS; \
    cmake --build /tmp/cyclonedds-cxx/build -j"$(nproc)"; \
    cmake --install /tmp/cyclonedds-cxx/build; \
    ldconfig; \
    rm -rf /tmp/cyclonedds-cxx

ENV CYCLONEDDS_HOME=/usr/local/lib/cmake/CycloneDDS
ENV CycloneDDS_DIR=/usr/local/lib/cmake/CycloneDDS
ENV CMAKE_PREFIX_PATH=/usr/local:/usr/local/lib/cmake/CycloneDDS:/usr/local/lib/cmake

# Install Python Unitree SDK2 package used by the MuJoCo simulator/client examples.
COPY unitree_mujoco_dockerized/unitree_sdk2_python/ /tmp/unitree_sdk2_python/
RUN cd /tmp/unitree_sdk2_python && python3 -m pip install --no-cache-dir .
RUN SDK_PATH="$(python3 -c 'import unitree_sdk2py, os; print(os.path.dirname(unitree_sdk2py.__file__))')" && \
    cp -r /tmp/unitree_sdk2_python/unitree_sdk2py/* "${SDK_PATH}/" && \
    find "${SDK_PATH}" -type d -exec sh -c 'd="$1"; if ls "$d"/*.py >/dev/null 2>&1 && [ ! -f "$d/__init__.py" ]; then touch "$d/__init__.py"; fi' _ {} \; && \
    rm -rf /tmp/unitree_sdk2_python

# Build and install the C++ Unitree SDK (submodule in unitree_mujoco_dockerized/unitree_sdk2).
COPY unitree_mujoco_dockerized/unitree_sdk2/ /tmp/unitree_sdk2/
RUN set -e; \
    cmake -S /tmp/unitree_sdk2 -B /tmp/unitree_sdk2/build \
      -DCMAKE_BUILD_TYPE=Release \
      -DCMAKE_PREFIX_PATH=/usr/local; \
    cmake --build /tmp/unitree_sdk2/build -j"$(nproc)"; \
    cmake --install /tmp/unitree_sdk2/build; \
    ldconfig; \
    rm -rf /tmp/unitree_sdk2

# Copy RL-MJLab submodule into image and apply local overlay (if any) from controller workspace.
COPY unitree_mujoco_dockerized/unitree_rl_mjlab/ /opt/unitree_rl_mjlab/
COPY unitree_mujoco_dockerized/mujoco_ws/unitree_g1_controller/rlmjlab_overlay/ /opt/unitree_rl_mjlab/
RUN set -e; \
    export CMAKE_PREFIX_PATH="/usr/local:${CMAKE_PREFIX_PATH}"; \
    export LDFLAGS="-L/usr/local/lib -Wl,-rpath,/usr/local/lib"; \
    cmake -S /opt/unitree_rl_mjlab/deploy/robots/g1 -B /opt/unitree_rl_mjlab/deploy/robots/g1/build \
      -DCMAKE_BUILD_TYPE=Release \
      -DCMAKE_PREFIX_PATH=/usr/local; \
    cmake --build /opt/unitree_rl_mjlab/deploy/robots/g1/build -j"$(nproc)"; \
    test -x /opt/unitree_rl_mjlab/deploy/robots/g1/build/g1_ctrl

RUN mkdir -p /workspace
WORKDIR /workspace

COPY unitree_mujoco_dockerized/unitree_mujoco/ /workspace/unitree_mujoco/
COPY unitree_mujoco_dockerized/unitree_sdk2_python/ /workspace/unitree_sdk2_python/
COPY unitree_mujoco_dockerized/unitree_ros/robots/g1_description/ /workspace/unitree_ros/robots/g1_description/

ENV PYTHONPATH=/workspace/unitree_mujoco/simulate_python

RUN mkdir -p /usr/local/bin/entrypoint
COPY unitree_mujoco_dockerized/entrypoint/*.sh /usr/local/bin/entrypoint/
RUN chmod +x /usr/local/bin/entrypoint/*.sh

ENV ROBOT=g1
ENV ROBOT_SCENE=/workspace/unitree_mujoco/unitree_robots/g1/scene.xml
ENV DOMAIN_ID=0
ENV INTERFACE=lo
ENV USE_JOYSTICK=0
ENV JOYSTICK_TYPE=xbox
ENV PRINT_SCENE_INFORMATION=true
ENV ENABLE_ELASTIC_BAND=false

RUN mkdir -p /workspace/output

WORKDIR /workspace
ENTRYPOINT ["/usr/local/bin/entrypoint/g1_entrypoint.sh"]
CMD ["launch"]
