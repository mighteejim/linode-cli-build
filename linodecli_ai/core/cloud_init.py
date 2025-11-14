"""Cloud-init generation."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Optional

import yaml


@dataclass
class CloudInitConfig:
    container_image: str
    internal_port: int
    external_port: int
    env_vars: Dict[str, str] = field(default_factory=dict)
    post_start_script: Optional[str] = None
    command: Optional[str] = None


def generate_cloud_init(config: CloudInitConfig) -> str:
    """Render a cloud-init YAML payload for provisioning the Linode."""
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

    doc = {
        "write_files": write_files,
        "runcmd": [["/bin/sh", "/usr/local/bin/start-container.sh"]],
    }
    return "#cloud-config\n" + yaml.safe_dump(doc, sort_keys=False)


def _render_env_file(env_vars: Dict[str, str]) -> str:
    """Render dotenv content sorted by key."""
    lines = []
    for key in sorted(env_vars.keys()):
        value = env_vars[key]
        lines.append(f"{key}={value}")
    return "\n".join(lines) + ("\n" if lines else "")


def _render_start_script(config: CloudInitConfig) -> str:
    lines = [
        "#!/bin/sh",
        "set -eu",
        "CONTAINER_NAME=app",
        "IMAGE=\"%s\"" % config.container_image,
        "EXTERNAL_PORT=%d" % config.external_port,
        "INTERNAL_PORT=%d" % config.internal_port,
        "",
        "install_docker() {",
        "  if command -v docker >/dev/null 2>&1; then",
        "    return",
        "  fi",
        "  if command -v apt-get >/dev/null 2>&1; then",
        "    export DEBIAN_FRONTEND=noninteractive",
        "    apt-get update",
        "    apt-get install -y docker.io",
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
        "docker run -d \\",
        "  --name \"$CONTAINER_NAME\" \\",
        "  --restart unless-stopped \\",
        "  --env-file /etc/build-ai.env \\",
        "  -p ${EXTERNAL_PORT}:${INTERNAL_PORT} \\",
    ]
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
