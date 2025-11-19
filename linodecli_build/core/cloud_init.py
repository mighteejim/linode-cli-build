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
    capability_manager: cap_module.CapabilityManager
    env_vars: Dict[str, str] = field(default_factory=dict)
    post_start_script: Optional[str] = None
    command: Optional[str] = None
    custom_setup_script: Optional[str] = None
    custom_files: List[Dict[str, Any]] = field(default_factory=list)
    volumes: List[str] = field(default_factory=list)


def generate_cloud_init(config: CloudInitConfig) -> str:
    """Render a cloud-init YAML payload for provisioning the Linode.
    
    Uses CapabilityManager to assemble cloud-init configuration.
    """
    
    # Get capability fragments from the capability manager
    cap_fragments = config.capability_manager.assemble_fragments()
    
    # Build write_files
    write_files = [
        {
            "path": "/etc/build.env",
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
    if cap_fragments.bootcmd:
        doc["bootcmd"] = cap_fragments.bootcmd
    
    return "#cloud-config\n" + yaml.safe_dump(doc, sort_keys=False)


def _render_env_file(env_vars: Dict[str, str]) -> str:
    """Render dotenv content sorted by key."""
    lines = []
    for key in sorted(env_vars.keys()):
        value = env_vars[key]
        lines.append(f"{key}={value}")
    return "\n".join(lines) + ("\n" if lines else "")


def _render_start_script(config: CloudInitConfig) -> str:
    """Render the container start script.
    
    Capabilities handle all system setup (Docker, GPU, etc.).
    This script just pulls and runs the container.
    """
    # Check if GPU capability is present
    requires_gpu = False
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
        "",
    ]
    
    # Add GPU verification if needed
    if requires_gpu:
        lines.extend([
            "# Wait for NVIDIA drivers to be ready",
            "echo \"Waiting for NVIDIA drivers...\"",
            "for i in 1 2 3 4 5 6 7 8 9 10; do",
            "  if nvidia-smi >/dev/null 2>&1; then",
            "    echo \"✓ NVIDIA drivers ready\"",
            "    nvidia-smi --query-gpu=name,driver_version --format=csv,noheader || true",
            "    break",
            "  fi",
            "  echo \"  Attempt $i/10: waiting for drivers...\"",
            "  sleep 5",
            "done",
            "",
            "# Verify NVIDIA drivers are working",
            "if ! nvidia-smi >/dev/null 2>&1; then",
            "  echo \"ERROR: NVIDIA drivers not available after 50 seconds\" >&2",
            "  echo \"This may require a system reboot to initialize the GPU\" >&2",
            "  exit 1",
            "fi",
            "",
        ])
    
    lines.extend([
        "# Wait for Docker to be ready",
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
        ". /etc/build.env",
        "set +a",
    ]
    
    # Build docker run command
    docker_run_lines = [
        "",
        "docker run -d \\",
        "  --name \"$CONTAINER_NAME\" \\",
        "  --restart unless-stopped \\",
        "  --env-file /etc/build.env \\",
        "  -p ${EXTERNAL_PORT}:${INTERNAL_PORT} \\",
    ]
    
    # Add volume mounts from template config
    for volume in config.volumes:
        docker_run_lines.append(f"  -v {volume} \\")
    
    # Add GPU support if GPU capability is present
    if requires_gpu:
        docker_run_lines.append("  --gpus all \\")
    
    lines.extend(docker_run_lines)
    image_line = "  \"$IMAGE\""
    if config.command:
        lines.append(image_line + " \\")
        lines.append(f"  {config.command}")
    else:
        lines.append(image_line)

    # Add post-start hook if provided
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
