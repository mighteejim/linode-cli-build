"""Core deployment operations - reusable logic for both CLI and TUI."""

from __future__ import annotations

import base64
import datetime as dt
import re
import secrets
import string
import time
from pathlib import Path
from typing import Dict, Optional, Callable

import yaml

from . import capabilities
from . import cloud_init
from . import env as env_core
from . import registry
from . import templates as template_core
from .deployment_tracker import DeploymentTracker


def deploy_project(
    config,
    directory: Path,
    overrides: Optional[Dict] = None,
    wait: bool = False,
    progress_callback: Optional[Callable] = None
) -> Dict:
    """Core deployment logic.
    
    Args:
        config: PluginContext with CLI client
        directory: Project directory containing deploy.yml
        overrides: Dict with region, linode_type, app_name, env_name, root_pass, etc.
        wait: Whether to wait for deployment completion
        progress_callback: Function called with status updates (msg, severity)
        
    Returns:
        Dict with deployment info (deployment_id, instance_id, ipv4, hostname, etc.)
    """
    overrides = overrides or {}
    
    # Helper for progress updates
    def update_progress(msg: str, severity: str = "info"):
        if progress_callback:
            progress_callback(msg, severity)
    
    # Load deploy.yml
    deploy_file = directory / "deploy.yml"
    
    if not deploy_file.exists():
        raise FileNotFoundError(f"No deploy.yml found in {directory}")
    
    try:
        with open(deploy_file, 'r') as f:
            data = yaml.safe_load(f)
    except Exception as e:
        raise ValueError(f"Error loading deploy.yml: {e}")
    
    if not isinstance(data, dict):
        raise ValueError("deploy.yml must contain a YAML object")
    
    # Create Template instance from deploy.yml
    template = template_core.Template(
        name=data.get("name", "unknown"),
        display_name=data.get("display_name", data.get("name", "Unknown")),
        version=str(data.get("version", "0.0.0")),
        description=data.get("description", "").strip(),
        data=data,
    )
    
    linode_cfg = template.data.get("deploy", {}).get("linode", {})
    container_cfg = linode_cfg.get("container", {})

    # Get deployment settings (allow overrides)
    region = overrides.get("region") or linode_cfg.get("region_default")
    linode_type = overrides.get("linode_type") or linode_cfg.get("type_default")
    app_name = overrides.get("app_name") or data.get("name", "app")
    env_name = overrides.get("env_name") or "default"
    container_image = overrides.get("container_image") or container_cfg.get("image")

    if not region or not linode_type or not container_image:
        raise ValueError("Region, Linode type, and container image must be defined in deploy.yml.")

    update_progress(f"Loading configuration for {app_name}...", "info")

    # Read environment file
    env_file = overrides.get("env_file") or ".env"
    env_values = _read_env_file(directory / env_file, template)
    template_env = container_cfg.get("env", {})
    
    # Expand ${VAR} references in template env values
    expanded_template_env = {}
    for key, value in template_env.items():
        if isinstance(value, str) and "${" in value:
            def replace_var(match):
                var_expr = match.group(1)
                if ":-" in var_expr:
                    var_name, default = var_expr.split(":-", 1)
                    return env_values.get(var_name.strip(), default.strip())
                else:
                    return env_values.get(var_expr.strip(), "")
            value = re.sub(r'\$\{([^}]+)\}', replace_var, value)
        expanded_template_env[key] = value
    
    merged_env = {**expanded_template_env, **env_values}
    merged_env["BUILD_AI_APP_NAME"] = app_name
    merged_env["BUILD_AI_ENV"] = env_name

    internal_port = int(container_cfg.get("internal_port") or 8000)
    external_port = int(container_cfg.get("external_port") or 80)

    # Generate deployment_id before creating cloud-init config
    deployment_id = _generate_deployment_id()
    
    update_progress(f"Deployment ID: {deployment_id}", "success")

    # Create capability manager from template with deployment context
    capability_manager = capabilities.create_capability_manager(
        template.data,
        deployment_id=deployment_id,
        app_name=app_name
    )
    
    # Get custom setup from template
    setup_cfg = template.data.get("setup", {})
    custom_setup_script = setup_cfg.get("script")
    custom_files = []
    for file_spec in setup_cfg.get("files", []):
        custom_files.append({
            "path": file_spec.get("path"),
            "permissions": file_spec.get("permissions", "0644"),
            "owner": file_spec.get("owner", "root:root"),
            "content": file_spec.get("content", ""),
        })

    # Extract volumes from container config
    volumes = container_cfg.get("volumes", [])
    
    config_obj = cloud_init.CloudInitConfig(
        container_image=container_image,
        internal_port=internal_port,
        external_port=external_port,
        capability_manager=capability_manager,
        env_vars=merged_env,
        post_start_script=container_cfg.get("post_start_script"),
        command=container_cfg.get("command"),
        custom_setup_script=custom_setup_script,
        custom_files=custom_files,
        volumes=volumes,
    )
    user_data = cloud_init.generate_cloud_init(config_obj)

    # Use native CLI client
    client = config.client
    root_pass, password_file = _determine_root_password(
        overrides.get("root_pass"),
        directory
    )
    timestamp = dt.datetime.utcnow().strftime("%m%d%H%M")
    label = _build_label(app_name, env_name, timestamp)
    tags = _build_tags(app_name, env_name, template, deployment_id)

    base_image = (
        overrides.get("image")
        or linode_cfg.get("image")
        or "linode/ubuntu24.04"
    )
    
    update_progress(
        f"Creating Linode {linode_type} in {region} (image: {base_image})...",
        "info"
    )
    
    # Encode user_data as base64 for metadata
    b64_user_data = base64.b64encode(user_data.encode("utf-8")).decode("utf-8")
    
    # Create instance using CLI call_operation
    create_args = [
        '--type', linode_type,
        '--region', region,
        '--image', base_image,
        '--label', label,
        '--group', 'build',
        '--root_pass', root_pass,
        '--metadata.user_data', b64_user_data,
    ]
    
    # Add each tag as a separate --tags argument
    for tag in tags:
        create_args.extend(['--tags', tag])
    
    status, response = client.call_operation('linodes', 'create', create_args)
    
    if status != 200:
        raise RuntimeError(f"Failed to create Linode: {response}")
    
    instance = response
    linode_id = instance.get('id')
    ipv4 = _primary_ipv4(instance)
    hostname = _derive_hostname(ipv4)
    
    update_progress(f"Linode created with ID: {linode_id}", "success")
    
    # Save metadata using DeploymentTracker
    tracker = DeploymentTracker(client)
    health_cfg = container_cfg.get("health")
    metadata = {
        "deployment_id": deployment_id,
        "app_name": app_name,
        "env": env_name,
        "created_at": dt.datetime.utcnow().isoformat(),
        "created_from": str(directory.resolve()),
        "health_config": health_cfg,
        "hostname": hostname,
        "external_port": external_port,
        "internal_port": internal_port,
    }
    tracker.save_metadata(linode_id, metadata)

    record = {
        "deployment_id": deployment_id,
        "app_name": app_name,
        "env": env_name,
        "template": template.name,
        "template_version": template.version,
        "target": "linode",
        "region": region,
        "linode_type": linode_type,
        "linode_id": linode_id,
        "ipv4": ipv4,
        "hostname": hostname,
        "health": container_cfg.get("health"),
        "external_port": external_port,
        "internal_port": internal_port,
        "created_at": dt.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "last_status": instance.get('status', 'provisioning'),
    }
    registry.add_deployment(record)
    
    # Save state for TUI access
    state_dir = directory / ".linode"
    state_dir.mkdir(exist_ok=True)
    state_file = state_dir / "state.json"
    
    import json
    state_data = {
        "instance_id": linode_id,
        "app_name": app_name,
        "environment": env_name,
        "deployment_id": deployment_id,
        "created": dt.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "ipv4": ipv4,
        "hostname": hostname,
        "region": region,
        "linode_type": linode_type,
    }
    
    with open(state_file, 'w') as f:
        json.dump(state_data, f, indent=2)
    
    update_progress(f"State saved to: {state_file}", "info")

    if wait:
        update_progress("Waiting for Linode to reach running state...", "info")
        instance = _wait_for_instance_status(client, linode_id, desired="running")
        record["last_status"] = instance.get('status', 'running')
        registry.update_fields(deployment_id, {"last_status": record["last_status"]})
        update_progress(
            "✓ Linode is running. Container start-up can take several minutes.",
            "success"
        )

    # Create SSH helper if password file was created
    if password_file:
        _create_ssh_helper(ipv4, hostname, directory)
        update_progress(f"SSH helper created: {directory}/connect.sh", "success")
    
    update_progress(f"🚀 Deployed {template.display_name}", "success")

    # Return deployment info
    return {
        "deployment_id": deployment_id,
        "instance_id": linode_id,
        "ipv4": ipv4,
        "hostname": hostname,
        "region": region,
        "linode_type": linode_type,
        "app_name": app_name,
        "env_name": env_name,
        "external_port": external_port,
        "internal_port": internal_port,
        "password_file": str(password_file) if password_file else None,
        "template_name": template.name,
        "template_display_name": template.display_name,
        "template_version": template.version,
    }


def _read_env_file(env_path: Path, template) -> Dict[str, str]:
    """Read and validate environment file."""
    requirements = [
        env_core.EnvRequirement(name=item.get("name"), description=item.get("description", ""))
        for item in template.data.get("env", {}).get("required", [])
    ]
    if not env_path.exists():
        if requirements:
            raise env_core.EnvError(f"Missing env file {env_path} required for template.")
        return {}
    env_values = env_core.load_env_file(str(env_path))
    env_core.ensure_required(env_values, requirements)
    return env_values


def _primary_ipv4(instance) -> str:
    """Extract primary IPv4 from instance dict."""
    ipv4_list = instance.get('ipv4', [])
    if ipv4_list and len(ipv4_list) > 0:
        return ipv4_list[0]
    raise RuntimeError("Instance missing IPv4 address.")


def _derive_hostname(ipv4: str) -> str:
    """Derive hostname from IPv4 address."""
    octets = ipv4.split(".")
    return f"{'-'.join(octets)}.ip.linodeusercontent.com"


def _wait_for_instance_status(
    client,
    instance_id: int,
    desired: str = "running",
    timeout: int = 600,
    poll: int = 10
):
    """Poll Linode until it reaches the desired status or timeout."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        status, response = client.call_operation('linodes', 'view', [str(instance_id)])
        if status == 200:
            instance = response
            if instance.get('status') == desired:
                return instance
        time.sleep(poll)
    raise RuntimeError(
        f"Linode {instance_id} did not reach status {desired} within {timeout}s"
    )


_SAFE_CHAR_PATTERN = re.compile(r"[^A-Za-z0-9_.-]")


def _slugify(value: str, max_length: int) -> str:
    """Convert string to safe slug."""
    text = _SAFE_CHAR_PATTERN.sub("-", value)
    text = re.sub("-+", "-", text).strip("-")
    text = text or "x"
    return text[:max_length]


def _build_label(app_name: str, env_name: str, timestamp: str) -> str:
    """Build a Linode label (max 64 chars, alphanumeric + hyphens)."""
    base = f"build-{_slugify(app_name, 10)}-{_slugify(env_name, 6)}-{timestamp}"
    return base[:64]


def _build_tag(prefix: str, value: str) -> str:
    """Build a tag ensuring total length doesn't exceed 50 characters."""
    max_total = 50
    prefix_with_colon = f"{prefix}:"
    available_for_value = max_total - len(prefix_with_colon)
    
    if available_for_value < 1:
        return _slugify(value, max_total)
    
    safe_value = _slugify(value, available_for_value)
    return f"{prefix}:{safe_value}"


def _build_tags(app_name: str, env_name: str, template, deployment_id: str):
    """Build tags ensuring each doesn't exceed 50 characters."""
    return [
        _build_tag("build-id", deployment_id),
        _build_tag("build-app", app_name),
        _build_tag("build-env", env_name),
        _build_tag("build-tmpl", template.name),
    ]


def _determine_root_password(provided: Optional[str], directory: Path):
    """Determine root password - use provided or generate new."""
    if provided:
        return provided, None
    password = _generate_root_password()
    password_path = directory / "linode-root-password.txt"
    password_path.write_text(password + "\n", encoding="utf-8")
    return password, password_path


def _create_ssh_helper(ipv4: str, hostname: str, directory: Path) -> None:
    """Create a connect.sh script to easily SSH into the Linode."""
    connect_script = directory / "connect.sh"
    
    script_content = f"""#!/bin/bash
# SSH connection helper for {hostname}

HOST="{ipv4}"
PASSWORD_FILE="linode-root-password.txt"

# Check if sshpass is available
if command -v sshpass &> /dev/null; then
    # Use sshpass for automatic login
    if [ -f "$PASSWORD_FILE" ]; then
        PASSWORD=$(cat "$PASSWORD_FILE")
        echo "Connecting to root@$HOST..."
        sshpass -p "$PASSWORD" ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null root@$HOST
    else
        echo "Error: $PASSWORD_FILE not found"
        exit 1
    fi
else
    # sshpass not available, show manual instructions
    echo "Connecting to root@$HOST..."
    echo ""
    if [ -f "$PASSWORD_FILE" ]; then
        echo "Root password (will be copied to clipboard if pbcopy available):"
        cat "$PASSWORD_FILE"
        
        # Try to copy to clipboard (macOS)
        if command -v pbcopy &> /dev/null; then
            cat "$PASSWORD_FILE" | tr -d '\\n' | pbcopy
            echo ""
            echo "✓ Password copied to clipboard!"
        fi
    fi
    echo ""
    echo "Tip: Install sshpass for automatic login:"
    echo "  macOS: brew install hudochenkov/sshpass/sshpass"
    echo "  Linux: sudo apt install sshpass"
    echo ""
    ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null root@$HOST
fi
"""
    
    connect_script.write_text(script_content, encoding="utf-8")
    connect_script.chmod(0o755)  # Make executable


def _generate_deployment_id() -> str:
    """Generate unique deployment ID (8 chars, alphanumeric lowercase)."""
    alphabet = string.ascii_lowercase + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(8))


def _generate_root_password(length: int = 24) -> str:
    """Generate a secure root password."""
    alphabet = string.ascii_lowercase + string.ascii_uppercase + string.digits + "!@#$%^&*-_=+"
    while True:
        pwd = "".join(secrets.choice(alphabet) for _ in range(length))
        if (
            any(c.islower() for c in pwd)
            and any(c.isupper() for c in pwd)
            and any(c.isdigit() for c in pwd)
            and any(c in "!@#$%^&*-_=+" for c in pwd)
        ):
            return pwd
