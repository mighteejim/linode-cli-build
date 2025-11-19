"""Template loading utilities."""

from __future__ import annotations

from dataclasses import dataclass
from importlib import resources
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from . import user_templates


class TemplateError(RuntimeError):
    """Base template error."""


class TemplateNotFoundError(TemplateError):
    """Raised when a template cannot be found."""


@dataclass(frozen=True)
class TemplateRecord:
    """Metadata for a single template."""

    name: str
    path: str
    source: str = "bundled"  # "bundled" or "user"


@dataclass
class Template:
    """Hydrated template definition."""

    name: str
    display_name: str
    version: str
    description: str
    data: Dict[str, Any]

    def manifest_defaults(self) -> Dict[str, Any]:
        """Return defaults used when writing deploy.yml.
        
        NOTE: This method is deprecated and no longer used by init.py.
        The init command now writes the complete template data directly to deploy.yml.
        Kept for backward compatibility only.
        """
        deploy = self.data.get("deploy", {})
        linode = deploy.get("linode", {})
        return {
            "template": {"name": self.name, "version": self.version},
            "deploy": {
                "region": linode.get("region_default"),
                "linode_type": linode.get("type_default"),
                "app_name": self.name,
                "env": "default",
            },
            "env": {"file": ".env"},
        }


_INDEX: Optional[List[TemplateRecord]] = None
_TEMPLATE_CACHE: Dict[str, Template] = {}


def list_template_records() -> List[TemplateRecord]:
    """Return metadata for bundled AND user templates.
    
    User templates are listed first (so they appear first in list).
    If a user template has the same name as a bundled template,
    only the user template is included (user overrides bundled).
    """
    # Load user templates first
    user_records = user_templates.load_user_templates_index()
    
    # Load bundled templates
    bundled_records = _load_bundled_template_records()
    
    # Merge: user templates first, skip bundled if name conflicts
    seen_names = {r.name for r in user_records}
    merged = list(user_records)
    for record in bundled_records:
        if record.name not in seen_names:
            merged.append(record)
    
    return merged


def _load_bundled_template_records() -> List[TemplateRecord]:
    """Load only bundled templates from package resources."""
    global _INDEX
    if _INDEX is None:
        index_data = _load_yaml_resource("templates/index.yml") or {}
        records: List[TemplateRecord] = []
        for entry in index_data.get("templates", []):
            if "name" not in entry or "path" not in entry:
                continue
            records.append(
                TemplateRecord(
                    name=entry["name"],
                    path=entry["path"],
                    source="bundled"
                )
            )
        _INDEX = records
    return list(_INDEX)


def load_template(name: str, version: Optional[str] = None) -> Template:
    """Load a template by name (user or bundled).
    
    Args:
        name: Template name (optionally with version like 'name@0.1.0')
        version: Version is parsed but not enforced for bundled templates
    
    Returns:
        Loaded Template instance
        
    Loading order:
    1. Check in-memory cache
    2. Try user templates first
    3. Fall back to bundled templates
    """
    # Parse version from name if present
    if '@' in name:
        name, parsed_version = name.split('@', 1)
        if version is None:
            version = parsed_version
    
    normalized = name.strip()
    cache_key = f"{normalized}@{version}" if version else normalized
    
    # Check in-memory cache
    if cache_key in _TEMPLATE_CACHE:
        return _TEMPLATE_CACHE[cache_key]
    
    # Try user templates first
    user_path = user_templates.get_user_template_path(normalized)
    if user_path:
        template_file = user_path / "template.yml"
        if template_file.exists():
            with open(template_file, 'r') as f:
                data = yaml.safe_load(f)
            
            if isinstance(data, dict):
                template = Template(
                    name=data.get("name", normalized),
                    display_name=data.get("display_name", normalized),
                    version=str(data.get("version", "0.0.0")),
                    description=data.get("description", "").strip(),
                    data=data,
                )
                _TEMPLATE_CACHE[cache_key] = template
                return template
    
    # Fall back to bundled templates
    record = _find_record(normalized)
    if record is None:
        raise TemplateNotFoundError(f"Unknown template: {name}")

    data = _load_yaml_resource(record.path)
    if not isinstance(data, dict):
        raise TemplateError(f"Template {name} is not a valid YAML object")

    template = Template(
        name=data.get("name", normalized),
        display_name=data.get("display_name", normalized),
        version=str(data.get("version", "0.0.0")),
        description=data.get("description", "").strip(),
        data=data,
    )
    _TEMPLATE_CACHE[cache_key] = template
    return template


def _find_record(name: str) -> Optional[TemplateRecord]:
    for record in list_template_records():
        if record.name == name:
            return record
    return None


def _load_yaml_resource(relative_path: str) -> Any:
    """Load a YAML document stored with the package."""
    try:
        resource = resources.files("linodecli_build").joinpath(relative_path)
    except FileNotFoundError as exc:
        raise TemplateError(f"Missing resource: {relative_path}") from exc

    if not resource.is_file():
        raise TemplateError(f"Resource is not a file: {relative_path}")

    contents = resource.read_text(encoding="utf-8")
    return yaml.safe_load(contents)
