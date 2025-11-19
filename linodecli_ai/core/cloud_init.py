"""Cloud-init generation."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Optional, Any, List

import yaml

from . import capabilities as cap_module


@dataclass
class CloudInitConfig:
    container_image: str
    internal_port: int
    external_port: int
    env_vars: Dict[str, str] = field(default_factory=dict)
    post_start_script: Optional[str] = None
    command: Optional[str] = None
    requires_gpu: bool = False
    capability_manager: Optional[cap_module.CapabilityManager] = None
    custom_setup_script: Optional[str] = None
    custom_files: List[Dict[str, Any]] = field(default_factory=list)


def generate_cloud_init(config: CloudInitConfig) -> str:
    """Render a cloud-init YAML payload for provisioning the Linode.
    
    This function supports two modes:
    1. Capability-based (new): Uses CapabilityManager to assemble cloud-init
    2. Legacy (backward compatible): Uses hardcoded GPU/Docker logic
    """
    
    # Get capability fragments if using new system
    cap_fragments = None
    if config.capability_manager:
        cap_fragments = config.capability_manager.assemble_fragments()
    
    # Build bootcmd (capability-based or legacy)
    bootcmd = []
    if cap_fragments:
        bootcmd.extend(cap_fragments.bootcmd)
    elif config.requires_gpu:
        # Legacy GPU bootcmd
        bootcmd = [
            "echo 'blacklist nouveau' > /etc/modprobe.d/blacklist-nouveau.conf",
            "echo 'options nouveau modeset=0' >> /etc/modprobe.d/blacklist-nouveau.conf",
            "update-initramfs -u || true",
        ]
    
    # Build write_files
    write_files = [
        {
            "path": "/etc/build-ai.env",
            "permissions": "0600",
            "owner": "root:root",
            "content": _render_env_file(config.env_vars),
        },
        {
            "path": "/usr/local/bin/start-container.sh",
            "permissions": "0755",
            "owner": "root:root",
            "content": _render_start_script(config),
        },
    ]
    
    # Add capability write_files
    if cap_fragments:
        write_files.extend(cap_fragments.write_files)
    
    # Add custom files
    write_files.extend(config.custom_files)
    
    # Add custom setup script if provided
    if config.custom_setup_script:
        write_files.append({
            "path": "/usr/local/bin/custom-setup.sh",
            "permissions": "0755",
            "owner": "root:root",
            "content": config.custom_setup_script,
        })

    # Build runcmd
    runcmd = []
    
    # Add capability runcmd
    if cap_fragments:
        # Add packages installation first
        if cap_fragments.packages:
            packages_str = " ".join(cap_fragments.packages)
            runcmd.extend([
                "export DEBIAN_FRONTEND=noninteractive",
                "apt-get update -qq || true",
                f"apt-get install -y -qq {packages_str} || true",
            ])
        # Then run capability commands
        runcmd.extend(cap_fragments.runcmd)
    
    # Run custom setup script if provided
    if config.custom_setup_script:
        runcmd.append("/bin/sh /usr/local/bin/custom-setup.sh")
    
    # Finally run the container start script
    runcmd.append(["/bin/sh", "/usr/local/bin/start-container.sh"])

    doc = {
        "write_files": write_files,
        "runcmd": runcmd,
    }
    
    # Add bootcmd if needed
    if bootcmd:
        doc["bootcmd"] = bootcmd
    
    return "#cloud-config\n" + yaml.safe_dump(doc, sort_keys=False)


def _render_env_file(env_vars: Dict[str, str]) -> str:
    """Render dotenv content sorted by key."""
    lines = []
    for key in sorted(env_vars.keys()):
        value = env_vars[key]
        lines.append(f"{key}={value}")
    return "\n".join(lines) + ("\n" if lines else "")


def _render_start_script(config: CloudInitConfig) -> str:
    # Check if GPU is required from either legacy flag or capabilities
    requires_gpu = config.requires_gpu
    if config.capability_manager:
        # Check if any capability is GPU-related
        for cap in config.capability_manager.capabilities:
            if cap.name() in ["gpu-nvidia", "gpu-amd"]:
                requires_gpu = True
                break
    
    lines = [
        "#!/bin/sh",
        "set -eu",
        "CONTAINER_NAME=app",
        "IMAGE=\"%s\"" % config.container_image,
        "EXTERNAL_PORT=%d" % config.external_port,
        "INTERNAL_PORT=%d" % config.internal_port,
        "REQUIRES_GPU=%s" % ("true" if requires_gpu else "false"),
        "",
        "install_docker() {",
        "  if command -v docker >/dev/null 2>&1; then",
        "    return",
        "  fi",
        "  if command -v apt-get >/dev/null 2>&1; then",
        "    export DEBIAN_FRONTEND=noninteractive",
        "    apt-get update",
        "    apt-get install -y docker.io",
        "    # Configure for faster pulls",
        "    mkdir -p /etc/docker",
        "    echo '{\"max-concurrent-downloads\": 10}' > /etc/docker/daemon.json",
        "  elif command -v apk >/dev/null 2>&1; then",
        "    apk update",
        "    apk add docker",
        "    if command -v rc-update >/dev/null 2>&1; then",
        "      rc-update add docker boot || true",
        "    fi",
        "  elif command -v dnf >/dev/null 2>&1; then",
        "    dnf install -y docker",
        "  elif command -v yum >/dev/null 2>&1; then",
        "    yum install -y docker",
        "  else",
        "    curl -fsSL https://get.docker.com | sh",
        "  fi",
        "}",
        "",
        "install_nvidia_drivers() {",
        "  if [ \"$REQUIRES_GPU\" != \"true\" ]; then",
        "    return",
        "  fi",
        "  # Check if drivers already working",
        "  if nvidia-smi >/dev/null 2>&1; then",
        "    echo \"✓ NVIDIA drivers already installed\"",
        "    nvidia-smi --query-gpu=name,driver_version --format=csv,noheader || true",
        "    return",
        "  fi",
        "  # Check if NVIDIA GPU exists",
        "  if ! lspci | grep -i nvidia >/dev/null 2>&1; then",
        "    echo \"Warning: No NVIDIA GPU detected\" >&2",
        "    return",
        "  fi",
        "  # Install drivers",
        "  echo \"Installing NVIDIA drivers...\"",
        "  export DEBIAN_FRONTEND=noninteractive",
        "  apt-get update -qq",
        "  if apt-get install -y -qq nvidia-driver-535 nvidia-utils-535; then",
        "    echo \"✓ NVIDIA drivers installed\"",
        "  else",
        "    apt-get install -y -qq ubuntu-drivers-common",
        "    ubuntu-drivers autoinstall >/dev/null 2>&1 || true",
        "  fi",
        "  # Verify and restart Docker if drivers work",
        "  if nvidia-smi >/dev/null 2>&1; then",
        "    echo \"✓ NVIDIA drivers working\"",
        "    nvidia-smi --query-gpu=name,driver_version --format=csv,noheader || true",
        "    systemctl restart docker",
        "    sleep 2",
        "  else",
        "    echo \"⚠️  GPU may require reboot to initialize\"",
        "  fi",
        "}",
        "",
        "install_nvidia_container_toolkit() {",
        "  if [ \"$REQUIRES_GPU\" != \"true\" ]; then",
        "    return",
        "  fi",
        "  if command -v nvidia-ctk >/dev/null 2>&1; then",
        "    return",
        "  fi",
        "  echo \"Installing NVIDIA Container Toolkit...\"",
        "  curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg",
        "  curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list | \\",
        "    sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | \\",
        "    tee /etc/apt/sources.list.d/nvidia-container-toolkit.list",
        "  apt-get update -qq",
        "  apt-get install -y -qq nvidia-container-toolkit",
        "  nvidia-ctk runtime configure --runtime=docker",
        "  systemctl restart docker",
        "  sleep 2",
        "  echo \"✓ NVIDIA Container Toolkit installed\"",
        "}",
        "",
        "start_docker() {",
        "  if command -v systemctl >/dev/null 2>&1; then",
        "    systemctl enable docker || true",
        "    systemctl start docker",
        "  elif command -v rc-service >/dev/null 2>&1; then",
        "    rc-update add cgroups boot >/dev/null 2>&1 || true",
        "    rc-service cgroups start >/dev/null 2>&1 || true",
        "    rc-service docker start || rc-service docker restart",
        "  else",
        "    service docker start 2>/dev/null || dockerd >/var/log/dockerd.log 2>&1 &",
        "    sleep 5",
        "  fi",
        "}",
        "",
        "install_docker",
        "start_docker",
        "install_nvidia_container_toolkit",
        "install_nvidia_drivers",
        "",
        "i=0",
        "while [ $i -lt 30 ]; do",
        "  if docker info >/dev/null 2>&1; then",
        "    break",
        "  fi",
        "  i=$((i + 1))",
        "  sleep 2",
        "done",
        "if ! docker info >/dev/null 2>&1; then",
        "  echo \"Docker daemon unavailable\" >&2",
        "  exit 1",
        "fi",
        "",
        "docker pull \"$IMAGE\"",
        "docker rm -f \"$CONTAINER_NAME\" >/dev/null 2>&1 || true",
        "",
        "# Source env file for variable expansion in command",
        "set -a",
        ". /etc/build-ai.env",
        "set +a",
    ]
    
    # Build docker run command with GPU support if needed
    docker_run_lines = [
        "",
        "docker run -d \\",
        "  --name \"$CONTAINER_NAME\" \\",
        "  --restart unless-stopped \\",
        "  --env-file /etc/build-ai.env \\",
        "  -p ${EXTERNAL_PORT}:${INTERNAL_PORT} \\",
    ]
    
    if requires_gpu:
        docker_run_lines.append("  --gpus all \\")
    
    lines.extend(docker_run_lines)
    image_line = "  \"$IMAGE\""
    if config.command:
        lines.append(image_line + " \\")
        lines.append(f"  {config.command}")
    else:
        lines.append(image_line)

    if config.post_start_script:
        lines.extend(
            [
                "",
                "# Template post-start hook",
                "cat <<'HOOK' >/usr/local/bin/post-start-hook.sh",
                config.post_start_script.rstrip(),
                "HOOK",
                "chmod +x /usr/local/bin/post-start-hook.sh",
                "sh /usr/local/bin/post-start-hook.sh",
            ]
        )

    lines.append("")
    return "\n".join(lines)
