"""Template registry for remote template management."""

from __future__ import annotations

import json
import os
import shutil
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.request import urlopen
from urllib.error import URLError

import yaml


DEFAULT_REGISTRY_URL = (
    "https://raw.githubusercontent.com/linode/linode-cli-ai-templates/main/index.yml"
)
DEFAULT_CACHE_DIR = Path.home() / ".config" / "linode-cli.d" / "ai" / "templates"
DEFAULT_UPDATE_INTERVAL = 86400  # 24 hours in seconds


@dataclass
class RemoteTemplateEntry:
    """Metadata for a remote template."""

    name: str
    display_name: str
    version: str
    path: str
    description: str
    tags: List[str]
    verified: bool
    author: str
    min_plugin_version: str
    compatibility: Optional[List[str]] = None


@dataclass
class TemplateRegistry:
    """Remote template registry metadata."""

    version: str
    updated: str
    repository: str
    templates: List[RemoteTemplateEntry]


class RegistryError(RuntimeError):
    """Base registry error."""


class RegistryNetworkError(RegistryError):
    """Network error when fetching registry."""


class RegistryConfig:
    """Configuration for template registry."""

    def __init__(
        self,
        registry_url: str = DEFAULT_REGISTRY_URL,
        cache_dir: Path = DEFAULT_CACHE_DIR,
        auto_update: bool = True,
        update_check_interval: int = DEFAULT_UPDATE_INTERVAL,
    ):
        self.registry_url = registry_url
        self.cache_dir = cache_dir
        self.auto_update = auto_update
        self.update_check_interval = update_check_interval

    @classmethod
    def load_from_file(cls, config_path: Optional[Path] = None) -> RegistryConfig:
        """Load registry configuration from file."""
        if config_path is None:
            config_path = Path.home() / ".config" / "linode-cli.d" / "ai" / "config.yml"

        if not config_path.exists():
            return cls()  # Return defaults

        try:
            with open(config_path) as f:
                config_data = yaml.safe_load(f)

            templates_config = config_data.get("templates", {})
            return cls(
                registry_url=templates_config.get("registry_url", DEFAULT_REGISTRY_URL),
                cache_dir=Path(
                    templates_config.get("cache_dir", DEFAULT_CACHE_DIR)
                ).expanduser(),
                auto_update=templates_config.get("auto_update", True),
                update_check_interval=templates_config.get(
                    "update_check_interval", DEFAULT_UPDATE_INTERVAL
                ),
            )
        except Exception:
            # If config is invalid, return defaults
            return cls()


class TemplateRegistryClient:
    """Client for interacting with remote template registry."""

    def __init__(self, config: Optional[RegistryConfig] = None):
        self.config = config or RegistryConfig.load_from_file()
        self.config.cache_dir.mkdir(parents=True, exist_ok=True)

    @property
    def _index_cache_path(self) -> Path:
        """Path to cached index.yml."""
        return self.config.cache_dir / "index.yml"

    @property
    def _last_update_path(self) -> Path:
        """Path to last update timestamp file."""
        return self.config.cache_dir / ".last_update"

    def fetch_index(self, force_update: bool = False) -> TemplateRegistry:
        """
        Fetch template index from remote or cache.

        Args:
            force_update: Force refresh from remote even if cache is fresh

        Returns:
            TemplateRegistry with all available templates
        """
        # Check if we should use cached version
        if not force_update and self._is_cache_fresh():
            try:
                return self._load_cached_index()
            except Exception:
                pass  # Fall through to fetch from remote

        # Fetch from remote
        try:
            return self._fetch_remote_index()
        except RegistryNetworkError:
            # If network fails, try to use cached version even if stale
            if self._index_cache_path.exists():
                try:
                    return self._load_cached_index()
                except Exception:
                    pass
            raise

    def _is_cache_fresh(self) -> bool:
        """Check if cached index is still fresh."""
        if not self._index_cache_path.exists():
            return False

        if not self._last_update_path.exists():
            return False

        try:
            with open(self._last_update_path) as f:
                last_update = float(f.read().strip())
        except Exception:
            return False

        age = time.time() - last_update
        return age < self.config.update_check_interval

    def _load_cached_index(self) -> TemplateRegistry:
        """Load index from cache."""
        with open(self._index_cache_path) as f:
            data = yaml.safe_load(f)

        return self._parse_index(data)

    def _fetch_remote_index(self) -> TemplateRegistry:
        """Fetch index from remote URL."""
        try:
            with urlopen(self.config.registry_url, timeout=10) as response:
                data = yaml.safe_load(response.read())
        except (URLError, TimeoutError) as e:
            raise RegistryNetworkError(f"Failed to fetch registry: {e}") from e

        registry = self._parse_index(data)

        # Cache the index
        self._cache_index(data)

        return registry

    def _cache_index(self, data: Dict[str, Any]) -> None:
        """Cache index data to disk."""
        with open(self._index_cache_path, "w") as f:
            yaml.dump(data, f)

        with open(self._last_update_path, "w") as f:
            f.write(str(time.time()))

    def _parse_index(self, data: Dict[str, Any]) -> TemplateRegistry:
        """Parse index data into TemplateRegistry."""
        templates = []
        for entry in data.get("templates", []):
            templates.append(
                RemoteTemplateEntry(
                    name=entry["name"],
                    display_name=entry.get("display_name", entry["name"]),
                    version=entry["version"],
                    path=entry["path"],
                    description=entry.get("description", ""),
                    tags=entry.get("tags", []),
                    verified=entry.get("verified", False),
                    author=entry.get("author", "Unknown"),
                    min_plugin_version=entry.get("min_plugin_version", "0.1.0"),
                    compatibility=entry.get("compatibility"),
                )
            )

        return TemplateRegistry(
            version=data.get("version", "unknown"),
            updated=data.get("updated", "unknown"),
            repository=data.get("repository", ""),
            templates=templates,
        )

    def download_template(
        self, name: str, version: Optional[str] = None
    ) -> Path:
        """
        Download a template from the registry.

        Args:
            name: Template name
            version: Specific version to download (None for latest)

        Returns:
            Path to downloaded template directory
        """
        # Fetch index to get template info
        registry = self.fetch_index()

        # Find matching template
        template_entry = None
        for entry in registry.templates:
            if entry.name == name:
                if version is None or entry.version == version:
                    template_entry = entry
                    break

        if template_entry is None:
            raise RegistryError(
                f"Template '{name}' not found in registry"
                + (f" (version {version})" if version else "")
            )

        # Download template files
        template_dir = self.config.cache_dir / name
        template_dir.mkdir(parents=True, exist_ok=True)

        # Construct base URL for template files
        base_url = registry.repository.replace(
            "github.com", "raw.githubusercontent.com"
        )
        if not base_url.endswith("main"):
            base_url += "/main"

        # Download template.yml
        template_yml_url = f"{base_url}/{template_entry.path}/template.yml"
        self._download_file(template_yml_url, template_dir / "template.yml")

        # Download docs/README.md
        docs_url = f"{base_url}/{template_entry.path}/docs/README.md"
        docs_dir = template_dir / "docs"
        docs_dir.mkdir(exist_ok=True)
        self._download_file(docs_url, docs_dir / "README.md")

        # Write metadata file
        metadata = {
            "name": template_entry.name,
            "version": template_entry.version,
            "downloaded_at": time.time(),
            "source": self.config.registry_url,
        }
        with open(template_dir / ".metadata.json", "w") as f:
            json.dump(metadata, f, indent=2)

        return template_dir

    def _download_file(self, url: str, dest: Path) -> None:
        """Download a file from URL to destination."""
        try:
            with urlopen(url, timeout=10) as response:
                dest.write_bytes(response.read())
        except (URLError, TimeoutError) as e:
            raise RegistryNetworkError(f"Failed to download {url}: {e}") from e

    def list_cached_templates(self) -> List[Dict[str, Any]]:
        """List templates that are cached locally."""
        cached = []

        if not self.config.cache_dir.exists():
            return cached

        for template_dir in self.config.cache_dir.iterdir():
            if not template_dir.is_dir():
                continue

            metadata_file = template_dir / ".metadata.json"
            if not metadata_file.exists():
                continue

            try:
                with open(metadata_file) as f:
                    metadata = json.load(f)
                cached.append(
                    {
                        "name": metadata.get("name", template_dir.name),
                        "version": metadata.get("version", "unknown"),
                        "path": str(template_dir),
                        "downloaded_at": metadata.get("downloaded_at"),
                    }
                )
            except Exception:
                continue

        return cached

    def remove_template(self, name: str) -> None:
        """Remove a cached template."""
        template_dir = self.config.cache_dir / name
        if template_dir.exists():
            shutil.rmtree(template_dir)

    def clear_cache(self) -> None:
        """Clear all cached templates and index."""
        if self.config.cache_dir.exists():
            shutil.rmtree(self.config.cache_dir)
        self.config.cache_dir.mkdir(parents=True, exist_ok=True)

    def update_templates(self, force: bool = False) -> int:
        """
        Update all cached templates to latest versions.

        Args:
            force: Force update even if cache is fresh

        Returns:
            Number of templates updated
        """
        # Get latest index
        registry = self.fetch_index(force_update=force)

        # Get list of cached templates
        cached = self.list_cached_templates()

        updated_count = 0

        for cached_template in cached:
            name = cached_template["name"]
            cached_version = cached_template["version"]

            # Find latest version in registry
            latest_entry = None
            for entry in registry.templates:
                if entry.name == name:
                    latest_entry = entry
                    break

            if latest_entry is None:
                # Template no longer in registry
                continue

            # Check if update needed
            if latest_entry.version != cached_version or force:
                try:
                    self.download_template(name, version=latest_entry.version)
                    updated_count += 1
                except Exception:
                    # Continue with other templates
                    continue

        return updated_count
