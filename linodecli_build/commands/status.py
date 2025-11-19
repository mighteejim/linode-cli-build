"""Implementation for `linode-cli build status`."""

from __future__ import annotations

import argparse
from typing import Dict, List, Tuple
from urllib import error as url_error
from urllib import request as url_request

from ..core import registry


def register(subparsers: argparse._SubParsersAction, config) -> None:
    parser = subparsers.add_parser("status", help="Show deployment status")
    parser.add_argument("--app", help="Filter by app name")
    parser.add_argument("--env", help="Filter by environment name")
    parser.add_argument("--verbose", action="store_true", help="Show detailed status info")
    parser.add_argument("--no-health", action="store_true", help="Skip HTTP health checks")
    parser.set_defaults(func=lambda args: _cmd_status(args, config))


def _cmd_status(args, config) -> None:
    deployments = registry.filter_deployments(app_name=args.app, env=args.env)
    if not deployments:
        print("No deployments found.")
        return

    client = config.client
    rows: List[Tuple[str, str, str, str, str]] = []

    for dep in deployments:
        status, detail = _fetch_status(client, dep, skip_health=args.no_health)
        registry.update_fields(dep["deployment_id"], {"last_status": status})
        url = _format_url(dep)
        rows.append((dep["app_name"], dep["env"], dep.get("region", "?"), status, url))
        if args.verbose:
            print(f"- {dep['app_name']} ({dep['env']}): {status}")
            print(f"  Linode ID: {dep.get('linode_id')}  Region: {dep.get('region')}")
            if detail:
                print(f"  Detail: {detail}")
            print(f"  URL: {url}")

    if not args.verbose:
        _print_table(("APP", "ENV", "REGION", "STATUS", "URL"), rows)


def _fetch_status(client, deployment: Dict, skip_health: bool) -> Tuple[str, str]:
    try:
        status, response = client.call_operation('linodes', 'view', [str(deployment["linode_id"])])
        if status != 200:
            return "error", f"Failed to fetch status: {response}"
        instance = response
    except Exception as exc:
        message = str(exc)
        if "Not Found" in message or "404" in message:
            return "missing", "Linode instance not found"
        return "error", message

    api_status = instance.get('status', 'unknown')
    mapped = _map_status(api_status)
    detail = f"Linode status: {api_status}"
    if mapped == "running" and not skip_health:
        health_cfg = deployment.get("health")
        if health_cfg and health_cfg.get("type") == "http":
            healthy, reason = _check_http_health(deployment, health_cfg)
            if healthy:
                detail = "HTTP health OK"
            else:
                mapped = "degraded"
                detail = reason
    return mapped, detail


def _map_status(api_status: str) -> str:
    status = (api_status or "").lower()
    if status in {"running"}:
        return "running"
    if status in {"provisioning", "booting", "rebooting", "migrating", "busy"}:
        return "provisioning"
    if status in {"offline", "stopped"}:
        return "stopped"
    if status in {"failed"}:
        return "failed"
    return "unknown"


def _check_http_health(deployment: Dict, health_cfg: Dict) -> Tuple[bool, str]:
    hostname = deployment.get("hostname")
    port = health_cfg.get("port", deployment.get("external_port", 80))
    path = health_cfg.get("path", "/")
    timeout = health_cfg.get("timeout_seconds", 3)
    url = f"http://{hostname}:{port}{path}"
    try:
        req = url_request.Request(url, method="GET")
        with url_request.urlopen(req, timeout=timeout) as resp:
            if resp.getcode() in health_cfg.get("success_codes", [200]):
                return True, "HTTP OK"
            return False, f"Unexpected status {resp.getcode()} for {url}"
    except url_error.URLError as exc:
        return False, f"Health check failed: {exc}"


def _format_url(dep: Dict) -> str:
    hostname = dep.get("hostname") or ""
    port = dep.get("external_port", 80)
    if port == 80:
        return f"http://{hostname}"
    return f"http://{hostname}:{port}"


def _print_table(headers, rows):
    widths = [len(h) for h in headers]
    for row in rows:
        widths = [max(widths[idx], len(str(value))) for idx, value in enumerate(row)]
    header_line = "  ".join(h.ljust(widths[idx]) for idx, h in enumerate(headers))
    print(header_line)
    print("  ".join("-" * width for width in widths))
    for row in rows:
        print("  ".join(str(value).ljust(widths[idx]) for idx, value in enumerate(row)))
