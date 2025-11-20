"""Implementation for `linode-cli build status`."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from urllib import error as url_error
from urllib import request as url_request

from ..core import registry
from ..core.deployment_tracker import DeploymentTracker


def register(subparsers: argparse._SubParsersAction, config) -> None:
    parser = subparsers.add_parser("status", help="Show deployment status")
    parser.add_argument("--app", help="Filter by app name")
    parser.add_argument("--env", help="Filter by environment name")
    parser.add_argument("--verbose", action="store_true", help="Show detailed status info")
    parser.add_argument("--no-health", action="store_true", help="Skip HTTP health checks")
    parser.set_defaults(func=lambda args: _cmd_status(args, config))


def _cmd_status(args, config) -> None:
    tracker = DeploymentTracker(config.client)
    
    # If no filters, try to auto-detect from current directory
    if not args.app and not args.env:
        deployment = tracker.find_deployment_for_directory(Path.cwd())
        if deployment:
            print(f"Found deployment from this directory:")
            _print_single_deployment(deployment, config.client, args.no_health, args.verbose)
            return
    
    # Otherwise list with filters
    deployments = tracker.list_deployments(app_name=args.app, env=args.env)
    
    if not deployments:
        print("No deployments found.")
        print("Run 'linode-cli build deploy' to create one.")
        return

    client = config.client
    rows: List[Tuple[str, str, str, str, str, str]] = []

    for dep in deployments:
        status, detail = _fetch_status(client, dep, skip_health=args.no_health)
        url = _format_url(dep)
        rows.append((
            dep['deployment_id'][:8],  # Show short ID
            dep["app_name"], 
            dep["env"], 
            dep.get("region", "?"), 
            status, 
            url
        ))
        if args.verbose:
            print(f"- {dep['app_name']} ({dep['env']}): {status}")
            print(f"  ID: {dep['deployment_id']}")
            print(f"  Linode ID: {dep.get('linode_id')}  Region: {dep.get('region')}")
            if detail:
                print(f"  Detail: {detail}")
            print(f"  URL: {url}")
            
            # Show BuildWatch info for running deployments
            if status == "running":
                hostname = dep.get("hostname")
                if hostname:
                    # Quick summary of BuildWatch status
                    events_data = _fetch_buildwatch_data(hostname, '/events?limit=5')
                    issues_data = _fetch_buildwatch_data(hostname, '/issues')
                    
                    if events_data and 'count' in events_data:
                        event_count = len(events_data.get('events', []))
                        if event_count > 0:
                            print(f"  Events: {event_count} recent container events")
                    
                    if issues_data and 'issues' in issues_data:
                        unresolved = [i for i in issues_data['issues'] if not i.get('resolved', False)]
                        if unresolved:
                            print(f"  Issues: ⚠ {len(unresolved)} unresolved issue(s) detected")
            print()

    if not args.verbose:
        _print_table(("ID", "APP", "ENV", "REGION", "STATUS", "URL"), rows)


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
        health_cfg = deployment.get("health_config")
        if health_cfg and health_cfg.get("type") == "http":
            healthy, reason = _check_http_health(deployment, health_cfg)
            if healthy:
                detail = "HTTP health OK"
            else:
                mapped = "degraded"
                detail = reason
    return mapped, detail


def _print_single_deployment(deployment: Dict, client, skip_health: bool, verbose: bool) -> None:
    """Print details of a single deployment."""
    status, detail = _fetch_status(client, deployment, skip_health)
    url = _format_url(deployment)
    
    print(f"  ID: {deployment['deployment_id']}")
    print(f"  App: {deployment['app_name']}")
    print(f"  Env: {deployment['env']}")
    print(f"  Linode ID: {deployment.get('linode_id')}")
    print(f"  Region: {deployment.get('region')}")
    print(f"  Status: {status}")
    print(f"  URL: {url}")
    if verbose and detail:
        print(f"  Detail: {detail}")
    
    # If verbose, try to fetch BuildWatch events and issues
    if verbose and status == "running":
        hostname = deployment.get("hostname")
        if hostname:
            print("\n  BuildWatch Status:")
            _print_buildwatch_info(hostname)


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


def _fetch_buildwatch_data(hostname: str, endpoint: str, timeout: int = 3) -> Optional[Dict]:
    """Fetch data from BuildWatch API.
    
    Args:
        hostname: Instance hostname/IP
        endpoint: API endpoint (e.g., '/status', '/events', '/issues')
        timeout: Request timeout in seconds
        
    Returns:
        Parsed JSON response or None on error
    """
    try:
        url = f"http://{hostname}:9090{endpoint}"
        req = url_request.Request(url)
        with url_request.urlopen(req, timeout=timeout) as response:
            data = response.read()
            return json.loads(data.decode('utf-8'))
    except Exception:
        return None


def _print_buildwatch_info(hostname: str) -> None:
    """Print BuildWatch events and issues.
    
    Args:
        hostname: Instance hostname/IP
    """
    # Try to fetch BuildWatch status
    status = _fetch_buildwatch_data(hostname, '/status')
    if not status:
        print("    BuildWatch service not available (may still be starting)")
        return
    
    # Fetch recent events
    events_data = _fetch_buildwatch_data(hostname, '/events?limit=10')
    if events_data and 'events' in events_data:
        events = events_data['events']
        if events:
            print("\n    Recent Events:")
            for event in events[:5]:  # Show last 5 events
                timestamp = event.get('timestamp', '').split('T')[1][:8] if 'T' in event.get('timestamp', '') else ''
                event_type = event.get('type', 'unknown')
                container = event.get('container', 'unknown')
                
                # Format event based on type
                if event_type == 'start':
                    print(f"      [{timestamp}] ✓ {container} started")
                elif event_type == 'die':
                    exit_code = event.get('exit_code', '')
                    print(f"      [{timestamp}] ✕ {container} died (exit code: {exit_code})")
                elif event_type == 'stop':
                    print(f"      [{timestamp}] ◼ {container} stopped")
                elif event_type == 'restart':
                    print(f"      [{timestamp}] ↻ {container} restarted")
                else:
                    print(f"      [{timestamp}] {container} {event_type}")
    
    # Fetch and display issues
    issues_data = _fetch_buildwatch_data(hostname, '/issues')
    if issues_data and 'issues' in issues_data:
        issues = issues_data['issues']
        unresolved = [i for i in issues if not i.get('resolved', False)]
        
        if unresolved:
            print("\n    Issues Detected:")
            for issue in unresolved[:5]:  # Show up to 5 issues
                severity = issue.get('severity', 'info')
                message = issue.get('message', 'Unknown issue')
                recommendation = issue.get('recommendation', '')
                
                if severity == 'critical':
                    print(f"      ✕ CRITICAL: {message}")
                elif severity == 'warning':
                    print(f"      ⚠ WARNING: {message}")
                else:
                    print(f"      ℹ INFO: {message}")
                
                if recommendation:
                    print(f"        → {recommendation}")
        else:
            print("    No issues detected")
