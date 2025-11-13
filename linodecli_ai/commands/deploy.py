"""Implementation for `linode-cli ai deploy`."""

from __future__ import annotations

import argparse
import datetime as dt
import re
import secrets
import string
import time
import uuid
from pathlib import Path
from typing import Dict, Optional

from ..core import cloud_init
from ..core import env as env_core
from ..core import linode_api
from ..core import project
from ..core import registry
from ..core import templates as template_core


def register(subparsers: argparse._SubParsersAction, config) -> None:
    parser = subparsers.add_parser("deploy", help="Deploy current project to Linode")
    parser.add_argument("--region", help="Override region for the Linode")
    parser.add_argument("--linode-type", help="Override Linode type/plan")
    parser.add_argument("--env-file", help="Override env file path")
    parser.add_argument("--image", help="Override container image")
    parser.add_argument("--app-name", help="Override app name for tagging")
    parser.add_argument("--env", dest="env_name", help="Override environment name")
    parser.add_argument("--root-pass", help="Root password to use for the Linode. If omitted, a secure password is generated and saved locally.")
    parser.add_argument(
        "--wait",
        action="store_true",
        help="Wait for Linode to reach running state and perform health check",
    )
    parser.set_defaults(func=lambda args: _cmd_deploy(args, config))


def _cmd_deploy(args, config) -> None:
    manifest = project.load_manifest()
    template_name = manifest.get("template", {}).get("name")
    if not template_name:
        raise project.ProjectManifestError("Manifest missing template.name")
    template = template_core.load_template(template_name)
    linode_cfg = template.data.get("deploy", {}).get("linode", {})
    container_cfg = linode_cfg.get("container", {})

    region = args.region or manifest.get("deploy", {}).get("region") or linode_cfg.get("region_default")
    linode_type = (
        args.linode_type or manifest.get("deploy", {}).get("linode_type") or linode_cfg.get("type_default")
    )
    app_name = args.app_name or manifest.get("deploy", {}).get("app_name") or template.name
    env_name = args.env_name or manifest.get("deploy", {}).get("env") or "default"
    container_image = args.image or container_cfg.get("image")

    if not region or not linode_type or not container_image:
        raise RuntimeError("Region, Linode type, and container image must be defined.")

    env_file = args.env_file or manifest.get("env", {}).get("file") or ".env"
    env_values = _read_env_file(env_file, template)
    template_env = container_cfg.get("env", {})
    merged_env = {**template_env, **env_values}
    merged_env["BUILD_AI_APP_NAME"] = app_name
    merged_env["BUILD_AI_ENV"] = env_name

    internal_port = int(container_cfg.get("internal_port") or 8000)
    external_port = int(container_cfg.get("external_port") or 80)

    config_obj = cloud_init.CloudInitConfig(
        container_image=container_image,
        internal_port=internal_port,
        external_port=external_port,
        env_vars=merged_env,
        post_start_script=container_cfg.get("post_start_script"),
        command=container_cfg.get("command"),
    )
    user_data = cloud_init.generate_cloud_init(config_obj)

    api = linode_api.LinodeAPI(config)
    root_pass, password_file = _determine_root_password(args.root_pass)
    deployment_id = str(uuid.uuid4())
    timestamp = dt.datetime.utcnow().strftime("%m%d%H%M")
    label = _build_label(app_name, env_name, timestamp)
    tags = _build_tags(app_name, env_name, template, deployment_id)

    base_image = linode_cfg.get("image", "linode/ubuntu24.04")
    print(f"Creating Linode {linode_type} in {region} (image: {base_image})...")
    instance = api.create_instance(
        region=region,
        linode_type=linode_type,
        image=base_image,
        label=label,
        tags=tags,
        user_data=user_data,
        root_pass=root_pass,
    )
    linode_id = instance["id"]
    ipv4 = _primary_ipv4(instance)
    hostname = api.derive_hostname(ipv4)

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
        "last_status": instance.get("status"),
    }
    registry.add_deployment(record)

    if args.wait:
        print("Waiting for Linode to reach running state...")
        instance = api.wait_for_status(linode_id, desired="running")
        record["last_status"] = instance.get("status")
        registry.update_fields(deployment_id, {"last_status": record["last_status"]})
        print(
            "Linode is running. Container start-up can take several minutes; "
            "run `linode-cli ai status` to monitor health."
        )

    print("")
    print(f"Deployed {template.display_name} (app: {app_name}, env: {env_name})")
    print(f"Linode ID: {linode_id}")
    print(f"IPv4:      {ipv4}")
    print(f"Hostname:  {hostname}")
    if password_file:
        print(f"Root password saved to: {password_file}")
    _print_next_steps(template, hostname)


def _read_env_file(path: str, template) -> Dict[str, str]:
    env_path = Path(path)
    requirements = [
        env_core.EnvRequirement(name=item.get("name"), description=item.get("description", ""))
        for item in template.data.get("env", {}).get("required", [])
    ]
    if not env_path.exists():
        if requirements:
            raise env_core.EnvError(f"Missing env file {path} required for template.")
        return {}
    env_values = env_core.load_env_file(str(env_path))
    env_core.ensure_required(env_values, requirements)
    return env_values


def _primary_ipv4(instance: Dict) -> str:
    ipv4_list = instance.get("ipv4") or []
    if isinstance(ipv4_list, list) and ipv4_list:
        return ipv4_list[0]
    raise linode_api.LinodeAPIError("Instance response missing IPv4 address.")


_SAFE_CHAR_PATTERN = re.compile(r"[^A-Za-z0-9_.-]")


def _slugify(value: str, max_length: int) -> str:
    text = _SAFE_CHAR_PATTERN.sub("-", value)
    text = re.sub("-+", "-", text).strip("-")
    text = text or "x"
    return text[:max_length]


def _build_label(app_name: str, env_name: str, timestamp: str) -> str:
    base = f"ai-{_slugify(app_name, 10)}-{_slugify(env_name, 6)}-{timestamp}"
    return base[:32]


def _build_tag(prefix: str, value: str) -> str:
    max_value_len = max(1, 50 - len(prefix) - 1)
    safe_value = _slugify(value, max_value_len)
    return f"{prefix}:{safe_value}"


def _build_tags(app_name: str, env_name: str, template, deployment_id: str):
    return [
        _build_tag("ai-app", app_name),
        _build_tag("ai-env", env_name),
        _build_tag("ai-tmpl", template.name),
        _build_tag("ai-tver", template.version),
        _build_tag("ai-deploy", deployment_id[:12]),
    ]


def _determine_root_password(provided: Optional[str]):
    if provided:
        return provided, None
    password = _generate_root_password()
    password_path = Path.cwd() / "linode-root-password.txt"
    password_path.write_text(password + "\n", encoding="utf-8")
    return password, password_path


def _generate_root_password(length: int = 24) -> str:
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


def _print_next_steps(template, hostname: str) -> None:
    guidance = template.data.get("guidance") or {}
    if not guidance:
        return

    summary = guidance.get("summary")
    examples = guidance.get("examples", [])
    print("")
    if summary:
        print(summary.strip())

    for example in examples:
        desc = example.get("description")
        command = example.get("command", "").replace("{host}", hostname)
        if desc:
            print(f"- {desc}:")
        if command:
            print(command.strip())
        print("")
