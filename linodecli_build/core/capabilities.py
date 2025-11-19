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
        
        # Install Docker using official convenience script
        fragments.runcmd.extend([
            # Install Docker
            "curl -fsSL https://get.docker.com -o get-docker.sh",
            "sh get-docker.sh",
            "rm get-docker.sh",
            "systemctl enable docker",
            "systemctl start docker",
        ])
        
        # Configure daemon.json if optimization is requested
        if self.optimize:
            fragments.write_files.append({
                "path": "/etc/docker/daemon.json",
                "permissions": "0644",
                "owner": "root:root",
                "content": '{"max-concurrent-downloads": 10}\n',
            })
            # Restart Docker to apply config
            fragments.runcmd.append("systemctl restart docker")
        
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
        fragments.runcmd.extend([
            # Install NVIDIA drivers
            "ubuntu-drivers devices || true",
            "ubuntu-drivers autoinstall || true",
            "",
            # Load NVIDIA kernel modules
            "modprobe nvidia || true",
            "modprobe nvidia-uvm || true",
            "",
            # Verify NVIDIA drivers are loaded
            "nvidia-smi || echo 'Warning: nvidia-smi not available yet'",
            "",
            # Install NVIDIA Container Toolkit
            "curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg",
            "curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list | sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | tee /etc/apt/sources.list.d/nvidia-container-toolkit.list",
            "apt-get update -qq",
            "apt-get install -y nvidia-container-toolkit",
            "nvidia-ctk runtime configure --runtime=docker",
            "systemctl restart docker || true",
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
