"""Capability system for declarative template requirements.

This module provides a capability-based system for templates to declare their
requirements (GPU, Docker, packages, etc.) without writing cloud-init scripts.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional


@dataclass
class CapabilityFragments:
    """Cloud-init fragments returned by a capability."""
    
    packages: List[str] = field(default_factory=list)
    """APT/YUM packages to install."""
    
    runcmd: List[str] = field(default_factory=list)
    """Shell commands to run."""
    
    write_files: List[Dict[str, Any]] = field(default_factory=list)
    """Files to write to the system."""
    
    bootcmd: List[str] = field(default_factory=list)
    """Commands to run at boot (before cloud-init)."""


class Capability(ABC):
    """Base class for all capabilities."""
    
    @abstractmethod
    def get_fragments(self) -> CapabilityFragments:
        """Return cloud-init fragments for this capability."""
        pass
    
    @abstractmethod
    def name(self) -> str:
        """Return the capability name."""
        pass
    
    def conflicts_with(self) -> List[str]:
        """Return list of conflicting capability names."""
        return []


class DockerCapability(Capability):
    """Provides Docker runtime support."""
    
    def __init__(self, optimize: bool = False):
        """Initialize Docker capability.
        
        Args:
            optimize: Enable parallel downloads (10 concurrent)
        """
        self.optimize = optimize
    
    def name(self) -> str:
        return "docker"
    
    def get_fragments(self) -> CapabilityFragments:
        fragments = CapabilityFragments()
        
        # Install Docker via apt packages
        fragments.packages.extend([
            "docker.io",
            "docker-compose",
        ])
        
        # Configure daemon.json if optimization is requested
        if self.optimize:
            fragments.write_files.append({
                "path": "/etc/docker/daemon.json",
                "permissions": "0644",
                "owner": "root:root",
                "content": '{"max-concurrent-downloads": 10}\n',
            })
        
        # Ensure Docker is enabled and started
        fragments.runcmd.extend([
            "systemctl enable docker",
            "systemctl start docker",
        ])
        
        return fragments


class GPUNvidiaCapability(Capability):
    """Provides NVIDIA GPU support with drivers and container toolkit."""
    
    def name(self) -> str:
        return "gpu-nvidia"
    
    def conflicts_with(self) -> List[str]:
        return ["gpu-amd"]
    
    def get_fragments(self) -> CapabilityFragments:
        fragments = CapabilityFragments()
        
        # Blacklist Nouveau driver early
        fragments.bootcmd.extend([
            "echo 'blacklist nouveau' > /etc/modprobe.d/blacklist-nouveau.conf",
            "echo 'options nouveau modeset=0' >> /etc/modprobe.d/blacklist-nouveau.conf",
            "update-initramfs -u || true",
        ])
        
        # Install NVIDIA drivers and container toolkit
        fragments.packages.append("ubuntu-drivers-common")
        
        fragments.runcmd.extend([
            # Install NVIDIA drivers - try specific version first, fallback to autoinstall
            "export DEBIAN_FRONTEND=noninteractive",
            "apt-get update -qq",
            "",
            "# Try to install nvidia-driver-535 (known stable version)",
            "if apt-get install -y -qq nvidia-driver-535 nvidia-utils-535 2>/dev/null; then",
            "  echo 'Installed nvidia-driver-535'",
            "else",
            "  echo 'Falling back to ubuntu-drivers autoinstall'",
            "  ubuntu-drivers devices || true",
            "  ubuntu-drivers autoinstall || true",
            "fi",
            "",
            "# Wait for driver installation to complete",
            "sleep 10",
            "",
            "# Try to load kernel modules with retries",
            "for i in 1 2 3 4 5 6 7 8 9 10; do",
            "  if modprobe nvidia 2>/dev/null; then",
            "    echo 'nvidia module loaded'",
            "    break",
            "  fi",
            "  echo \"Attempt $i/10: waiting for nvidia module...\"",
            "  sleep 3",
            "done",
            "",
            "modprobe nvidia-uvm 2>/dev/null || true",
            "",
            "# Verify NVIDIA drivers are working",
            "for i in 1 2 3 4 5; do",
            "  if nvidia-smi 2>/dev/null; then",
            "    echo '✓ NVIDIA drivers working'",
            "    nvidia-smi --query-gpu=name,driver_version --format=csv,noheader || true",
            "    break",
            "  fi",
            "  echo \"Attempt $i/5: waiting for nvidia-smi...\"",
            "  sleep 5",
            "done",
            "",
            "# Install NVIDIA Container Toolkit",
            "curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg",
            "curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list | sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | tee /etc/apt/sources.list.d/nvidia-container-toolkit.list",
            "apt-get update -qq",
            "apt-get install -y nvidia-container-toolkit",
            "nvidia-ctk runtime configure --runtime=docker",
            "systemctl restart docker",
            "",
            "# Final wait for Docker to be ready with GPU support",
            "sleep 5",
        ])
        
        return fragments


class PythonCapability(Capability):
    """Provides Python runtime."""
    
    def __init__(self, version: str = "3.11"):
        """Initialize Python capability.
        
        Args:
            version: Python version (e.g., "3.11", "3.10")
        """
        self.version = version
    
    def name(self) -> str:
        return f"python-{self.version}"
    
    def get_fragments(self) -> CapabilityFragments:
        fragments = CapabilityFragments()
        
        # Install Python via deadsnakes PPA for Ubuntu
        package_name = f"python{self.version}"
        fragments.packages.extend([
            package_name,
            f"{package_name}-venv",
            f"{package_name}-dev",
            "python3-pip",
        ])
        
        fragments.runcmd.extend([
            # Add deadsnakes PPA for latest Python versions
            "add-apt-repository -y ppa:deadsnakes/ppa || true",
            "apt-get update -qq || true",
        ])
        
        return fragments


class NodeJSCapability(Capability):
    """Provides Node.js runtime."""
    
    def __init__(self, version: str = "18"):
        """Initialize Node.js capability.
        
        Args:
            version: Node.js major version (e.g., "18", "20")
        """
        self.version = version
    
    def name(self) -> str:
        return f"nodejs-{self.version}"
    
    def get_fragments(self) -> CapabilityFragments:
        fragments = CapabilityFragments()
        
        # Install Node.js from NodeSource
        fragments.runcmd.extend([
            f"curl -fsSL https://deb.nodesource.com/setup_{self.version}.x | bash -",
            "apt-get install -y nodejs",
        ])
        
        return fragments


class RedisCapability(Capability):
    """Provides Redis server."""
    
    def name(self) -> str:
        return "redis"
    
    def get_fragments(self) -> CapabilityFragments:
        fragments = CapabilityFragments()
        
        fragments.packages.append("redis-server")
        fragments.runcmd.extend([
            "systemctl enable redis-server",
            "systemctl start redis-server",
        ])
        
        return fragments


class PostgreSQLCapability(Capability):
    """Provides PostgreSQL server."""
    
    def __init__(self, version: str = "14"):
        """Initialize PostgreSQL capability.
        
        Args:
            version: PostgreSQL version (e.g., "14", "15")
        """
        self.version = version
    
    def name(self) -> str:
        return f"postgresql-{self.version}"
    
    def get_fragments(self) -> CapabilityFragments:
        fragments = CapabilityFragments()
        
        fragments.packages.extend([
            f"postgresql-{self.version}",
            f"postgresql-client-{self.version}",
        ])
        
        fragments.runcmd.extend([
            f"systemctl enable postgresql",
            f"systemctl start postgresql",
        ])
        
        return fragments


class CustomPackagesCapability(Capability):
    """Provides custom system packages."""
    
    def __init__(self, packages: List[str]):
        """Initialize custom packages capability.
        
        Args:
            packages: List of package names to install
        """
        self.packages = packages
    
    def name(self) -> str:
        return "custom-packages"
    
    def get_fragments(self) -> CapabilityFragments:
        fragments = CapabilityFragments()
        fragments.packages.extend(self.packages)
        return fragments


class BuildWatchCapability(Capability):
    """Provides BuildWatch container monitoring service.
    
    BuildWatch monitors Docker events in real-time, detects issues,
    and provides an HTTP API for status and logs.
    
    The service script is downloaded from GitHub to avoid exceeding
    cloud-init's 16KB metadata limit.
    """
    
    # GitHub raw URL for build-watcher.py script
    # TODO: Update to 'main' branch once merged
    SCRIPT_URL = "https://raw.githubusercontent.com/linode/linode-cli-ai/tui/build-watcher.py"
    
    def __init__(self, deployment_id: str, app_name: str):
        """Initialize BuildWatch capability.
        
        Args:
            deployment_id: Unique deployment identifier
            app_name: Application name
        """
        self.deployment_id = deployment_id
        self.app_name = app_name
    
    def name(self) -> str:
        return "buildwatch"
    
    def get_fragments(self) -> CapabilityFragments:
        fragments = CapabilityFragments()
        
        # Write systemd unit and logrotate config (small files - inline is OK)
        # Note: BuildWatch runs completely independently - no Docker dependencies in systemd
        systemd_unit = f"""[Unit]
Description=BuildWatch - Container Monitoring Service
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
ExecStart=/usr/local/bin/build-watcher
Restart=on-failure
RestartSec=10
StandardOutput=journal
StandardError=journal
Environment="BUILD_DEPLOYMENT_ID={self.deployment_id}"
Environment="BUILD_APP_NAME={self.app_name}"

# Don't restart on success - only on actual failures
StartLimitBurst=5
StartLimitIntervalSec=300

[Install]
WantedBy=multi-user.target
"""
        
        logrotate_config = """/var/log/build-watcher/*.log {
    daily
    rotate 7
    compress
    delaycompress
    missingok
    notifempty
    create 0640 root root
}
"""
        
        fragments.write_files.extend([
            {
                "path": "/etc/systemd/system/build-watcher.service",
                "permissions": "0644",
                "owner": "root:root",
                "content": systemd_unit,
            },
            {
                "path": "/etc/logrotate.d/build-watcher",
                "permissions": "0644",
                "owner": "root:root",
                "content": logrotate_config,
            },
        ])
        
        # Download and setup BuildWatch service
        fragments.runcmd.extend([
            "# Create BuildWatch directories",
            "mkdir -p /var/log/build-watcher",
            "mkdir -p /var/lib/build-watcher",
            "",
            "# Download BuildWatch service script from GitHub with retry",
            "echo 'Downloading BuildWatch service...'",
            "for i in 1 2 3 4 5; do",
            f"  if curl -fsSL --connect-timeout 10 --max-time 30 {self.SCRIPT_URL} -o /usr/local/bin/build-watcher; then",
            "    echo 'BuildWatch script downloaded successfully'",
            "    break",
            "  else",
            "    echo \"Attempt $i/5: Failed to download BuildWatch script, retrying...\"",
            "    sleep 5",
            "  fi",
            "done",
            "",
            "# Verify the script was downloaded",
            "if [ ! -f /usr/local/bin/build-watcher ]; then",
            "  echo 'ERROR: BuildWatch script not found after download attempts' >&2",
            "  echo 'BuildWatch will not be available for this deployment' >&2",
            "  exit 0  # Don't fail cloud-init, just skip BuildWatch",
            "fi",
            "",
            "# Make script executable and verify it's valid Python",
            "chmod +x /usr/local/bin/build-watcher",
            "if ! head -1 /usr/local/bin/build-watcher | grep -q python; then",
            "  echo 'ERROR: Downloaded file does not appear to be a Python script' >&2",
            "  rm -f /usr/local/bin/build-watcher",
            "  exit 0  # Don't fail cloud-init",
            "fi",
            "",
            "# Enable and start BuildWatch service",
            "systemctl daemon-reload",
            "systemctl enable build-watcher",
            "systemctl start build-watcher",
            "sleep 2",
            "",
            "# Verify service started",
            "if systemctl is-active --quiet build-watcher; then",
            "  echo '✓ BuildWatch monitoring started successfully'",
            "else",
            "  echo '✗ BuildWatch failed to start' >&2",
            "  journalctl -u build-watcher -n 20 --no-pager",
            "fi",
        ])
        
        return fragments


class CapabilityManager:
    """Manages capabilities and assembles cloud-init components."""
    
    # Registry of available capability factories
    _CAPABILITY_MAP: Dict[str, type] = {
        "docker": DockerCapability,
        "docker-optimize": lambda: DockerCapability(optimize=True),
        "gpu-nvidia": GPUNvidiaCapability,
        "python-3.10": lambda: PythonCapability("3.10"),
        "python-3.11": lambda: PythonCapability("3.11"),
        "python-3.12": lambda: PythonCapability("3.12"),
        "nodejs-18": lambda: NodeJSCapability("18"),
        "nodejs-20": lambda: NodeJSCapability("20"),
        "redis": RedisCapability,
        "postgresql-14": lambda: PostgreSQLCapability("14"),
        "postgresql-15": lambda: PostgreSQLCapability("15"),
    }
    
    def __init__(self):
        self.capabilities: List[Capability] = []
    
    def add_from_config(self, capabilities_config: Dict[str, Any]) -> None:
        """Add capabilities from template configuration.
        
        Args:
            capabilities_config: The 'capabilities' section from template.yml
        """
        runtime = capabilities_config.get("runtime")
        features = capabilities_config.get("features", [])
        packages = capabilities_config.get("packages", [])
        
        # Add runtime capability
        if runtime:
            if runtime == "docker":
                self.add_capability("docker")
            elif runtime == "native":
                # Native runtime doesn't need special setup
                pass
            else:
                raise ValueError(f"Unknown runtime: {runtime}")
        
        # Add feature capabilities
        for feature in features:
            self.add_capability(feature)
        
        # Add custom packages
        if packages:
            custom_cap = CustomPackagesCapability(packages)
            self.capabilities.append(custom_cap)
    
    def add_capability(self, name: str) -> None:
        """Add a capability by name.
        
        Args:
            name: Capability name (e.g., "gpu-nvidia", "docker-optimize")
        """
        if name not in self._CAPABILITY_MAP:
            raise ValueError(f"Unknown capability: {name}")
        
        factory = self._CAPABILITY_MAP[name]
        capability = factory() if callable(factory) else factory
        
        # Check for conflicts
        for existing in self.capabilities:
            if existing.name() in capability.conflicts_with():
                raise ValueError(
                    f"Capability {name} conflicts with {existing.name()}"
                )
            if capability.name() in existing.conflicts_with():
                raise ValueError(
                    f"Capability {name} conflicts with {existing.name()}"
                )
        
        self.capabilities.append(capability)
    
    def add_buildwatch(self, deployment_id: str, app_name: str) -> None:
        """Add BuildWatch monitoring capability.
        
        BuildWatch is always added FIRST so it can start monitoring immediately.
        
        Args:
            deployment_id: Unique deployment identifier
            app_name: Application name
        """
        buildwatch_cap = BuildWatchCapability(deployment_id, app_name)
        # Insert at the beginning so it runs first
        self.capabilities.insert(0, buildwatch_cap)
    
    def assemble_fragments(self) -> CapabilityFragments:
        """Assemble all capability fragments into a single set.
        
        Returns:
            Combined cloud-init fragments from all capabilities
        """
        combined = CapabilityFragments()
        
        for capability in self.capabilities:
            fragments = capability.get_fragments()
            combined.packages.extend(fragments.packages)
            combined.runcmd.extend(fragments.runcmd)
            combined.write_files.extend(fragments.write_files)
            combined.bootcmd.extend(fragments.bootcmd)
        
        return combined


def create_capability_manager(template_data: Dict[str, Any]) -> Optional[CapabilityManager]:
    """Create a capability manager from template data.
    
    Args:
        template_data: Full template data dictionary
    
    Returns:
        CapabilityManager if template has capabilities, None otherwise
    """
    capabilities_config = template_data.get("capabilities")
    if not capabilities_config:
        return None
    
    manager = CapabilityManager()
    manager.add_from_config(capabilities_config)
    return manager
