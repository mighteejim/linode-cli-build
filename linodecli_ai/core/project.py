"""Project manifest helpers.

NOTE: This module is deprecated. The CLI no longer uses ai.linode.yml manifests.
Instead, deploy.yml files contain the complete deployment configuration.
Kept for backward compatibility only.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict

import yaml

# Deprecated: CLI now uses deploy.yml instead
DEFAULT_MANIFEST = "ai.linode.yml"


class ProjectManifestError(RuntimeError):
    """Raised for manifest issues."""


def load_manifest(path: str | None = None) -> Dict:
    """Load project manifest.
    
    NOTE: This function is deprecated. The CLI no longer uses ai.linode.yml.
    Deployments now read from deploy.yml which contains the complete configuration.
    Kept for backward compatibility only.
    """
    manifest_path = Path(path or DEFAULT_MANIFEST)
    if not manifest_path.exists():
        raise ProjectManifestError(f"Project manifest not found: {manifest_path}")
    data = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ProjectManifestError("Project manifest must be a YAML mapping")
    return data
