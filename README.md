# Unitree MuJoCo Dockerized

## Overview
This project runs Unitree MuJoCo simulation in Docker using:
- `unitree_mujoco` (simulator/models)
- `unitree_sdk2_python` (Python SDK bindings)
- X11 forwarding for GUI rendering

## Host Dependencies
Install required host tools (Ubuntu/Debian):

```bash
sudo apt-get update
sudo apt-get install -y \
  ca-certificates \
  curl \
  git \
  x11-xserver-utils
```

Install Docker Engine + Docker Compose plugin by following the official guide:

https://docs.docker.com/engine/install/ubuntu/

Optional: run Docker without `sudo`:

```bash
sudo usermod -aG docker $USER
newgrp docker
```

Allow local Docker containers to use X11 display:

```bash
xhost +local:docker
```

## Build Docker Image
From this directory:

```bash
git submodule update --init --recursive
docker compose build
```

## Launch Docker
Foreground:

```bash
docker compose up
```

Background:

```bash
docker compose up -d
```

Stop:

```bash
docker compose down
```
