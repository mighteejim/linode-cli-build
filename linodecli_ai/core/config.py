"""Configuration management for Linode CLI AI plugin."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

import yaml


DEFAULT_CONFIG_PATH = Path.home() / ".config" / "linode-cli.d" / "ai" / "config.yml"


@dataclass
class TemplateSource:
    """Configuration for a template source."""

    name: str
    url: str
    enabled: bool = True


@dataclass
class TemplatesConfig:
    """Configuration for template management."""

    registry_url: str = (
        "https://raw.githubusercontent.com/linode/linode-cli-ai-templates/main/index.yml"
    )
    cache_dir: str = str(Path.home() / ".config" / "linode-cli.d" / "ai" / "templates")
    auto_update: bool = True
    update_check_interval: int = 86400  # 24 hours
    sources: List[TemplateSource] = field(default_factory=list)

    def __post_init__(self):
        """Initialize default sources if none provided."""
        if not self.sources:
            self.sources = [
                TemplateSource(
                    name="official",
                    url=self.registry_url,
                    enabled=True,
                )
            ]


@dataclass
class AIConfig:
    """Main configuration for AI plugin."""

    templates: TemplatesConfig = field(default_factory=TemplatesConfig)


class ConfigManager:
    """Manager for AI plugin configuration."""

    def __init__(self, config_path: Optional[Path] = None):
        self.config_path = config_path or DEFAULT_CONFIG_PATH
        self._config: Optional[AIConfig] = None

    @property
    def config(self) -> AIConfig:
        """Get current configuration, loading if necessary."""
        if self._config is None:
            self._config = self.load()
        return self._config

    def load(self) -> AIConfig:
        """Load configuration from file."""
        if not self.config_path.exists():
            return AIConfig()

        try:
            with open(self.config_path) as f:
                data = yaml.safe_load(f) or {}

            templates_data = data.get("templates", {})
            sources_data = templates_data.get("sources", [])

            sources = []
            for source in sources_data:
                if isinstance(source, dict):
                    sources.append(
                        TemplateSource(
                            name=source.get("name", "unnamed"),
                            url=source["url"],
                            enabled=source.get("enabled", True),
                        )
                    )

            templates_config = TemplatesConfig(
                registry_url=templates_data.get(
                    "registry_url",
                    TemplatesConfig.registry_url,
                ),
                cache_dir=templates_data.get(
                    "cache_dir",
                    TemplatesConfig.cache_dir,
                ),
                auto_update=templates_data.get("auto_update", True),
                update_check_interval=templates_data.get("update_check_interval", 86400),
                sources=sources or None,  # Will trigger default in __post_init__
            )

            return AIConfig(templates=templates_config)

        except Exception:
            # If config is invalid, return defaults
            return AIConfig()

    def save(self, config: Optional[AIConfig] = None) -> None:
        """Save configuration to file."""
        if config is None:
            config = self.config

        # Ensure config directory exists
        self.config_path.parent.mkdir(parents=True, exist_ok=True)

        # Convert to dict for YAML serialization
        data = {
            "templates": {
                "registry_url": config.templates.registry_url,
                "cache_dir": config.templates.cache_dir,
                "auto_update": config.templates.auto_update,
                "update_check_interval": config.templates.update_check_interval,
                "sources": [
                    {
                        "name": source.name,
                        "url": source.url,
                        "enabled": source.enabled,
                    }
                    for source in config.templates.sources
                ],
            }
        }

        with open(self.config_path, "w") as f:
            yaml.dump(data, f, default_flow_style=False)

    def add_template_source(self, name: str, url: str, enabled: bool = True) -> None:
        """Add a new template source."""
        config = self.config

        # Check if source already exists
        for source in config.templates.sources:
            if source.name == name:
                # Update existing source
                source.url = url
                source.enabled = enabled
                self.save(config)
                return

        # Add new source
        config.templates.sources.append(TemplateSource(name=name, url=url, enabled=enabled))
        self.save(config)

    def remove_template_source(self, name: str) -> bool:
        """Remove a template source by name. Returns True if removed."""
        config = self.config
        original_length = len(config.templates.sources)

        config.templates.sources = [
            source for source in config.templates.sources if source.name != name
        ]

        if len(config.templates.sources) < original_length:
            self.save(config)
            return True
        return False

    def enable_template_source(self, name: str, enabled: bool = True) -> bool:
        """Enable or disable a template source. Returns True if found."""
        config = self.config

        for source in config.templates.sources:
            if source.name == name:
                source.enabled = enabled
                self.save(config)
                return True

        return False

    def get_enabled_sources(self) -> List[TemplateSource]:
        """Get list of enabled template sources."""
        return [
            source for source in self.config.templates.sources if source.enabled
        ]


def get_config_manager() -> ConfigManager:
    """Get singleton config manager instance."""
    return ConfigManager()
