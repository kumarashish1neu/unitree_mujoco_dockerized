# Unitree Mujoco + Python Docker Environment
FROM ubuntu:22.04
ARG DEBIAN_FRONTEND=noninteractive
ARG MUJOCO_VERSION=3.3.0

SHELL ["/bin/bash", "-c"]

# Install system dependencies
RUN apt-get update && apt-get install --no-install-recommends -y \
    build-essential \
    cmake \
    git \
    vim \
    wget \
    curl \
    python3-pip \
    python3-dev \
    libosmesa6-dev \
    libgl1-mesa-dev \
    libglfw3-dev \
    libglew-dev \
    libx11-dev \
    libxrandr-dev \
    libxcursor-dev \
    libxinerama-dev \
    libxi-dev \
    pkg-config \
    xvfb \
    ffmpeg \
    ca-certificates \
    tzdata \
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
    && rm -rf /var/lib/apt/lists/*

# Install MuJoCo
ARG MUJOCO_TARBALL=mujoco-${MUJOCO_VERSION}-linux-x86_64.tar.gz
ARG MUJOCO_URL=https://github.com/google-deepmind/mujoco/releases/download/${MUJOCO_VERSION}/${MUJOCO_TARBALL}

RUN mkdir -p /opt && \
    curl -fsSL "${MUJOCO_URL}" -o /tmp/mujoco.tar.gz && \
    tar -xzf /tmp/mujoco.tar.gz -C /opt && \
    mv /opt/mujoco-${MUJOCO_VERSION} /opt/mujoco && \
    rm -f /tmp/mujoco.tar.gz && \
    chmod +x /opt/mujoco/bin/simulate

RUN python3 -m pip install --no-cache-dir \
    mujoco==${MUJOCO_VERSION} \
    pygame \
    pyyaml \
    numpy \
    scipy \
    opencv-python \
    noise \
    cython

ENV MUJOCO_HOME=/opt/mujoco
ENV MUJOCO_MODEL_DEFAULT=/opt/mujoco/model/humanoid/humanoid.xml
ENV LD_LIBRARY_PATH=/opt/mujoco/bin:/usr/local/lib:/usr/lib:${LD_LIBRARY_PATH:-}
ENV PATH=/opt/mujoco/bin:${PATH}

RUN apt-get update && apt-get install --no-install-recommends -y \
    cyclonedds-dev \
    cyclonedds-tools \
    && rm -rf /var/lib/apt/lists/*

ENV CYCLONEDDS_HOME=/usr/lib/x86_64-linux-gnu/cmake/CycloneDDS
ENV CycloneDDS_DIR=/usr/lib/x86_64-linux-gnu/cmake/CycloneDDS
ENV CMAKE_PREFIX_PATH="/usr/lib/x86_64-linux-gnu/cmake/CycloneDDS;/usr/lib/x86_64-linux-gnu/cmake;/usr;${CMAKE_PREFIX_PATH}"

COPY unitree_sdk2_python/ /tmp/unitree_sdk2_python/
RUN cd /tmp/unitree_sdk2_python && \
    python3 -m pip install --no-cache-dir .

RUN SDK_PATH="$(python3 -c 'import unitree_sdk2py, os; print(os.path.dirname(unitree_sdk2py.__file__))')" && \
    cp -r /tmp/unitree_sdk2_python/unitree_sdk2py/* "${SDK_PATH}/" && \
    find "${SDK_PATH}" -type d -exec sh -c 'd="$1"; if ls "$d"/*.py >/dev/null 2>&1 && [ ! -f "$d/__init__.py" ]; then touch "$d/__init__.py"; fi' _ {} \; && \
    ls -la "${SDK_PATH}" && \
    ls -la "${SDK_PATH}/g1" && \
    ls -la "${SDK_PATH}/utils/lib"

RUN rm -rf /tmp/unitree_sdk2_python

RUN mkdir -p /workspace
WORKDIR /workspace

COPY unitree_mujoco/ /workspace/unitree_mujoco/
COPY unitree_sdk2_python/ /workspace/unitree_sdk2_python/

ENV PYTHONPATH="/workspace/unitree_mujoco/simulate_python:${PYTHONPATH}"

RUN mkdir -p /usr/local/bin/entrypoint
COPY ./entrypoint/*.sh /usr/local/bin/entrypoint/
RUN chmod +x /usr/local/bin/entrypoint/*.sh

ENV ROBOT=${ROBOT:-g1}
ENV ROBOT_SCENE=/workspace/unitree_mujoco/unitree_robots/${ROBOT:-g1}/scene.xml
ENV DOMAIN_ID=${DOMAIN_ID:-1}
ENV INTERFACE=${INTERFACE:-lo}
ENV USE_JOYSTICK=${USE_JOYSTICK:-0}
ENV JOYSTICK_TYPE=${JOYSTICK_TYPE:-xbox}
ENV PRINT_SCENE_INFORMATION=${PRINT_SCENE_INFORMATION:-true}
ENV ENABLE_ELASTIC_BAND=${ENABLE_ELASTIC_BAND:-false}

RUN mkdir -p /workspace/output

WORKDIR /workspace
ENTRYPOINT ["/usr/local/bin/entrypoint/g1_entrypoint.sh"]
CMD ["launch"]
