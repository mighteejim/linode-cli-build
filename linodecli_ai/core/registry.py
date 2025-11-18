"""Local deployment registry management."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Iterable, List, Optional

REGISTRY_FILENAME = "ai-deployments.json"


def registry_path() -> Path:
    """Return the path to the registry JSON file."""
    config_dir = Path.home() / ".config" / "linode-cli.d" / "ai"
    return config_dir / REGISTRY_FILENAME


def load_registry() -> Dict[str, List[Dict]]:
    """Load registry data from disk."""
    path = registry_path()
    if not path.exists():
        return {"deployments": []}
    contents = path.read_text(encoding="utf-8")
    if not contents.strip():
        return {"deployments": []}
    return json.loads(contents)


def save_registry(data: Dict[str, List[Dict]]) -> None:
    """Persist registry to disk."""
    path = registry_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")


def add_deployment(record: Dict) -> None:
    data = load_registry()
    data.setdefault("deployments", []).append(record)
    save_registry(data)


def update_deployment_status(deployment_id: str, status: str) -> None:
    update_fields(deployment_id, {"last_status": status})


def update_fields(deployment_id: str, fields: Dict) -> None:
    data = load_registry()
    for entry in data.get("deployments", []):
        if entry.get("deployment_id") == deployment_id:
            entry.update(fields)
            save_registry(data)
            return
    raise KeyError(f"Deployment not found: {deployment_id}")


def remove_deployment(deployment_id: str) -> None:
    data = load_registry()
    deployments = data.get("deployments", [])
    new_deployments = [d for d in deployments if d.get("deployment_id") != deployment_id]
    if len(new_deployments) == len(deployments):
        raise KeyError(f"Deployment not found: {deployment_id}")
    data["deployments"] = new_deployments
    save_registry(data)


def filter_deployments(
    app_name: Optional[str] = None, env: Optional[str] = None
) -> List[Dict]:
    """Return deployments filtered by app/env."""
    deployments = load_registry().get("deployments", [])
    result = []
    for entry in deployments:
        if app_name and entry.get("app_name") != app_name:
            continue
        if env and entry.get("env") != env:
            continue
        result.append(entry)
    return result
