"""Template loading utilities."""

from __future__ import annotations

from dataclasses import dataclass
from importlib import resources
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from .template_registry import TemplateRegistryClient, RegistryConfig


class TemplateError(RuntimeError):
    """Base template error."""


class TemplateNotFoundError(TemplateError):
    """Raised when a template cannot be found."""


@dataclass(frozen=True)
class TemplateRecord:
    """Metadata for a single template."""

    name: str
    path: str


@dataclass
class Template:
    """Hydrated template definition."""

    name: str
    display_name: str
    version: str
    description: str
    data: Dict[str, Any]

    def manifest_defaults(self) -> Dict[str, Any]:
        """Return defaults used when writing ai.linode.yml."""
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
    """Return metadata for every template listed in the index."""
    global _INDEX
    if _INDEX is None:
        index_data = _load_yaml_resource("templates/index.yml") or {}
        records: List[TemplateRecord] = []
        for entry in index_data.get("templates", []):
            if "name" not in entry or "path" not in entry:
                continue
            records.append(TemplateRecord(name=entry["name"], path=entry["path"]))
        _INDEX = records
    return list(_INDEX)


def load_template(name: str, version: Optional[str] = None) -> Template:
    """Load a specific template by name.
    
    Args:
        name: Template name (optionally with version like 'name@0.1.0')
        version: Specific version to load (overrides version in name)
    
    Returns:
        Loaded Template instance
        
    Loading order:
    1. Check cache
    2. Try to load from cached remote templates
    3. Fall back to bundled templates
    """
    # Parse version from name if present (e.g., 'template@0.1.0')
    if '@' in name:
        name, parsed_version = name.split('@', 1)
        if version is None:
            version = parsed_version
    
    normalized = name.strip()
    cache_key = f"{normalized}@{version}" if version else normalized
    
    if cache_key in _TEMPLATE_CACHE:
        return _TEMPLATE_CACHE[cache_key]
    
    # Try to load from cached remote templates first
    template = _load_from_remote_cache(normalized, version)
    if template is not None:
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


def _load_from_remote_cache(name: str, version: Optional[str] = None) -> Optional[Template]:
    """Try to load template from cached remote templates."""
    try:
        client = TemplateRegistryClient(RegistryConfig.load_from_file())
        cache_dir = client.config.cache_dir
        
        template_dir = cache_dir / name
        if not template_dir.exists():
            # Template not cached, try to download it
            try:
                template_dir = client.download_template(name, version=version)
            except Exception:
                # Download failed, return None to fall back to bundled
                return None
        
        template_yml = template_dir / "template.yml"
        if not template_yml.exists():
            return None
        
        with open(template_yml) as f:
            data = yaml.safe_load(f)
        
        if not isinstance(data, dict):
            return None
        
        # Check version match if specified
        if version and data.get("version") != version:
            return None
        
        return Template(
            name=data.get("name", name),
            display_name=data.get("display_name", name),
            version=str(data.get("version", "0.0.0")),
            description=data.get("description", "").strip(),
            data=data,
        )
    except Exception:
        # If anything fails, return None to fall back to bundled
        return None


def _load_yaml_resource(relative_path: str) -> Any:
    """Load a YAML document stored with the package."""
    try:
        resource = resources.files("linodecli_ai").joinpath(relative_path)
    except FileNotFoundError as exc:
        raise TemplateError(f"Missing resource: {relative_path}") from exc

    if not resource.is_file():
        raise TemplateError(f"Resource is not a file: {relative_path}")

    contents = resource.read_text(encoding="utf-8")
    return yaml.safe_load(contents)
