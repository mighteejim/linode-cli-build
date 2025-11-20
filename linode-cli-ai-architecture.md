# Linode CLI AI Architecture & Developer Guide

> **Purpose**: This document provides a comprehensive overview of the linode-cli-ai build system architecture, designed to help LLM agents and developers understand how the system works.

## Table of Contents

1. [System Overview](#system-overview)
2. [Project Structure](#project-structure)
3. [Core Concepts](#core-concepts)
4. [Command System](#command-system)
5. [Template System](#template-system)
6. [Capability System](#capability-system)
7. [Deployment Flow](#deployment-flow)
8. [Cloud-Init Generation](#cloud-init-generation)
9. [Key Components Deep Dive](#key-components-deep-dive)
10. [Extension Points](#extension-points)
11. [Data Flow Diagrams](#data-flow-diagrams)

---

## System Overview

### What It Does

linode-cli-ai is a **declarative deployment system** for AI/ML workloads on Linode cloud infrastructure. It:

- Deploys containerized AI services (LLMs, ML pipelines, embeddings, etc.)
- Manages infrastructure requirements declaratively (GPU, Docker, databases, etc.)
- Generates cloud-init configurations automatically
- Tracks deployments and their health status
- Provides monitoring through BuildWatch (optional)
- Offers a Terminal UI (TUI) for deployment management

### Architecture Pattern

The system follows a **template-driven, capability-based** architecture:

1. **Templates** define WHAT to deploy (container images, ports, env vars)
2. **Capabilities** define HOW to set up the infrastructure (GPU, Docker, Redis, etc.)
3. **Cloud-init** is generated from templates + capabilities
4. **Linode API** provisions instances with the generated configuration

### Technology Stack

- **Language**: Python 3.10+
- **CLI Framework**: argparse with custom plugin system
- **TUI Framework**: Textual (for interactive terminal UI)
- **Cloud Provider**: Linode API
- **Configuration**: YAML for templates and deployment configs
- **Cloud Provisioning**: cloud-init

---

## Project Structure

```
linode-cli-ai/
├── linodecli_build/              # Main package
│   ├── __init__.py
│   ├── commands/                 # Command implementations
│   │   ├── __init__.py
│   │   ├── base.py              # Base command class
│   │   ├── deploy.py            # Deploy command (main deployment logic)
│   │   ├── destroy.py           # Destroy/delete deployments
│   │   ├── init.py              # Initialize deployment directory
│   │   ├── scaffold.py          # Create new templates
│   │   ├── status.py            # Check deployment status
│   │   ├── templates.py         # Template management commands
│   │   └── tui.py               # Terminal UI commands
│   │
│   ├── core/                    # Core system components
│   │   ├── __init__.py
│   │   ├── build_watcher.py     # BuildWatch monitoring service
│   │   ├── capabilities.py      # Capability system (GPU, Docker, etc.)
│   │   ├── cloud_init.py        # Cloud-init generation
│   │   ├── colors.py            # Terminal color utilities
│   │   ├── deployment_tracker.py # Track deployment metadata
│   │   ├── env.py               # Environment variable handling
│   │   ├── llm_instructions_generator.py # LLM-assisted scaffolding
│   │   ├── registry.py          # Deployment registry (local DB)
│   │   ├── templates.py         # Template loading and management
│   │   └── user_templates.py    # User-installed template management
│   │
│   ├── templates/               # Bundled templates
│   │   ├── index.yml           # Template registry
│   │   ├── chat-agent/         # Ollama chat template
│   │   ├── embeddings-python/  # Python embeddings template
│   │   ├── llm-api/            # vLLM inference API template
│   │   └── ml-pipeline/        # PyTorch ML pipeline template
│   │
│   └── tui/                    # Terminal UI components
│       ├── __init__.py
│       ├── app.py              # Main TUI application
│       ├── api.py              # TUI API wrapper
│       ├── utils.py            # TUI utilities
│       ├── styles.tcss         # TUI CSS styles
│       ├── screens/            # TUI screens (home, status, logs, etc.)
│       └── widgets/            # Custom TUI widgets
│
├── docs/                       # Documentation
│   ├── buildwatch-usage.md
│   ├── buildwatch-quick-reference.md
│   ├── template-deployments.md
│   ├── template-development.md
│   └── template-quick-reference.md
│
├── scripts/                    # Utility scripts
│   └── build-watcher.py       # BuildWatch monitoring daemon
│
├── pyproject.toml             # Package configuration
└── README.md
```

---

## Core Concepts

### 1. Templates

**Templates** are YAML files that declaratively define AI service deployments.

**Key Sections:**
- `name` / `display_name` / `version`: Metadata
- `description`: What the template does
- `capabilities`: Infrastructure requirements (runtime, features, packages)
- `deploy`: Deployment configuration (region, instance type, container config)
- `env`: Environment variable requirements
- `setup`: Custom setup scripts and files (optional)
- `guidance`: Usage instructions and examples

**Example:**
```yaml
name: llm-api
display_name: LLM API
version: 0.1.0
description: vLLM inference API with GPU support

capabilities:
  runtime: docker
  features:
    - gpu-nvidia
    - docker-optimize
    - buildwatch

deploy:
  target: linode
  linode:
    image: linode/ubuntu22.04
    region_default: us-mia
    type_default: g6-standard-8
    container:
      image: vllm/vllm-openai:latest
      internal_port: 8000
      external_port: 80
      health:
        type: http
        path: /health
        port: 8000
        initial_delay_seconds: 180
```

### 2. Capabilities

**Capabilities** are composable infrastructure components that templates can declare.

**Capability Types:**
- **Runtime**: `docker`, `native`, `k3s`
- **Features**: `gpu-nvidia`, `redis`, `postgresql-14`, `buildwatch`, etc.
- **Custom Packages**: Any apt package

**How Capabilities Work:**
1. Templates declare capabilities in YAML
2. `CapabilityManager` resolves capabilities from registry
3. Each capability generates **cloud-init fragments** (packages, runcmd, write_files, bootcmd)
4. Fragments are assembled into complete cloud-init config

**Capability Interface:**
```python
class Capability(ABC):
    @abstractmethod
    def get_fragments(self) -> CapabilityFragments:
        """Return cloud-init fragments for this capability."""
        pass
    
    @abstractmethod
    def name(self) -> str:
        """Return the capability name."""
        pass
```

### 3. Cloud-Init

**Cloud-init** is the industry-standard system for cloud instance initialization. The system generates cloud-init YAML containing:

- **packages**: APT packages to install
- **runcmd**: Shell commands to run during boot
- **write_files**: Files to create on the instance
- **bootcmd**: Commands to run before cloud-init (early boot)

**Generation Flow:**
```
Template + Capabilities → CapabilityFragments → CloudInitConfig → YAML → Base64 → Linode Metadata
```

### 4. Deployments

**Deployments** are tracked instances of templates with:
- **Deployment ID**: Unique 8-character identifier (e.g., `a3b7f9k2`)
- **App Name**: User-defined application name
- **Environment**: Environment name (default, prod, staging, etc.)
- **Metadata**: Region, instance type, IPs, health status, etc.

**Storage:**
- Local registry: `~/.config/linode-cli.d/build/registry.json`
- Linode metadata: Stored on instance tags and metadata API
- Local state: `.linode/state.json` in deployment directory

---

## Command System

### Command Architecture

Commands are implemented as **modules** in `linodecli_build/commands/` with a consistent pattern:

```python
def register(subparsers, config):
    """Register command with argparse."""
    parser = subparsers.add_parser("commandname", help="...")
    parser.add_argument("--option", help="...")
    parser.set_defaults(func=lambda args: _cmd_commandname(args, config))

def _cmd_commandname(args, config):
    """Implement command logic."""
    # Command implementation
    pass
```

### Available Commands

#### Core Deployment Commands

**`init <template>`**
- Creates deployment directory from template
- Copies template.yml → deploy.yml (editable)
- Creates .env.example
- Prepares for customization before deploy

**`deploy`**
- Main deployment command
- Reads deploy.yml from current directory
- Generates cloud-init configuration
- Creates Linode instance via API
- Tracks deployment in registry
- Optionally waits for health check (--wait)

**`status [deployment-id]`**
- Shows deployment status
- Checks instance state
- Performs health checks
- Displays deployment metadata

**`destroy [deployment-id]`**
- Destroys Linode instance
- Removes from registry
- Cleans up local state

#### Template Management Commands

**`templates list`**
- Lists available templates (bundled + user-installed)

**`templates show <name>`**
- Displays template details

**`templates scaffold <name>`**
- Creates new template interactively
- Supports --llm-assist for AI-assisted creation

**`templates validate <path>`**
- Validates template YAML structure
- Checks required fields, capabilities, etc.

**`templates install <path>`**
- Installs user template to `~/.config/linode-cli.d/build/templates/`

**`templates uninstall <name>`**
- Removes user-installed template

#### TUI Commands

**`tui`**
- Launches interactive Terminal UI
- Shows deployment dashboard
- Real-time status monitoring
- Log viewing

---

## Template System

### Template Loading

**Location Priority:**
1. User templates: `~/.config/linode-cli.d/build/templates/`
2. Bundled templates: `linodecli_build/templates/`

**Template Discovery:**
```python
# templates.py
def discover_templates() -> List[Template]:
    """Discover all available templates."""
    # 1. Load bundled templates from index.yml
    # 2. Load user templates from user config dir
    # 3. Merge and deduplicate (user templates override bundled)
    return templates
```

### Template Structure

**Minimal Template:**
```yaml
name: my-template
display_name: My Template
version: 0.1.0
description: What it does

capabilities:
  runtime: docker

deploy:
  target: linode
  linode:
    image: linode/ubuntu24.04
    region_default: us-ord
    type_default: g6-standard-2
    container:
      image: myapp:latest
      internal_port: 8000
      external_port: 80
```

**Advanced Template with Everything:**
```yaml
name: advanced-template
display_name: Advanced Template
version: 1.0.0
description: Full-featured template

capabilities:
  runtime: docker
  features:
    - gpu-nvidia
    - redis
    - buildwatch
    - name: buildwatch  # Configured feature
      config:
        port: 9090
        log_retention_days: 14
  packages:
    - ffmpeg
    - libopencv-dev

deploy:
  target: linode
  linode:
    image: linode/ubuntu22.04
    region_default: us-mia
    type_default: g6-standard-8
    tags:
      - ai
      - gpu
    
    container:
      image: pytorch/pytorch:2.0-cuda11.7
      internal_port: 8000
      external_port: 80
      command: python /app/main.py --mode ${MODE}
      volumes:
        - /app:/app
        - /data:/data
      env:
        MODE: production
        DATABASE_URL: ${DATABASE_URL}
      
      post_start_script: |
        #!/bin/bash
        docker exec app python /app/warmup.py
      
      health:
        type: http
        path: /health
        port: 8000
        success_codes: [200]
        initial_delay_seconds: 120
        timeout_seconds: 10
        max_retries: 30

setup:
  script: |
    #!/bin/bash
    echo "Custom setup"
  
  files:
    - path: /app/config.yml
      permissions: "0644"
      content: |
        key: value

env:
  required:
    - name: DATABASE_URL
      description: Database connection string
  optional:
    - name: MODE
      description: Operating mode (production/development)

guidance:
  summary: How to use this service
  examples:
    - description: Health check
      command: curl http://{host}/health
```

### Template Initialization (init command)

**Flow:**
```
1. User runs: linode-cli build init llm-api
2. System loads template from registry
3. Creates directory with:
   - deploy.yml (copy of template.yml, editable)
   - .env.example (from template env requirements)
   - README (usage instructions)
4. User customizes deploy.yml and .env
5. User runs: linode-cli build deploy
```

**Key Point**: `deploy.yml` is the **working copy** that users can customize. The original template.yml remains unchanged.

---

## Capability System

### Capability Registry

Capabilities are registered in `CapabilityManager._CAPABILITY_MAP`:

```python
_CAPABILITY_MAP: Dict[str, type] = {
    "docker": DockerCapability,
    "docker-optimize": lambda: DockerCapability(optimize=True),
    "gpu-nvidia": GPUNvidiaCapability,
    "python-3.11": lambda: PythonCapability("3.11"),
    "redis": RedisCapability,
    "postgresql-14": lambda: PostgreSQLCapability("14"),
    "buildwatch": lambda config: BuildWatchCapability(
        deployment_id=config.get("deployment_id"),
        app_name=config.get("app_name"),
        port=config.get("port", 9090),
        log_retention_days=config.get("log_retention_days", 7),
        enable_metrics=config.get("enable_metrics", True)
    ),
}
```

### Capability Processing Flow

```
1. Template declares capabilities in YAML
2. deploy.py calls create_capability_manager(template_data, deployment_id, app_name)
3. CapabilityManager.add_from_config() processes features:
   - Simple string: "gpu-nvidia" → GPUNvidiaCapability()
   - Dict with config: {"name": "buildwatch", "config": {...}} → BuildWatchCapability(**config)
4. For context-aware capabilities (like buildwatch), inject deployment_id/app_name
5. Each capability.get_fragments() returns CapabilityFragments
6. assemble_fragments() combines all fragments
7. Fragments passed to cloud_init.generate_cloud_init()
```

### Built-in Capabilities

#### DockerCapability
**Purpose**: Installs Docker runtime

**Fragments:**
- Packages: `docker.io`, `docker-compose`
- Runcmd: Enable and start Docker service
- Optional: Configure daemon.json for parallel downloads

#### GPUNvidiaCapability
**Purpose**: Installs NVIDIA GPU drivers and container toolkit

**Fragments:**
- Bootcmd: Blacklist nouveau driver
- Packages: `ubuntu-drivers-common`
- Runcmd: Install nvidia-driver-535, load kernel modules, install nvidia-container-toolkit
- Verification: nvidia-smi health check

**Requirements**: Must use Ubuntu 22.04 base image (proven stable)

#### BuildWatchCapability (NEW - Optional)
**Purpose**: Container monitoring and issue detection

**Configuration:**
- `port`: HTTP API port (default: 9090)
- `log_retention_days`: Log rotation (default: 7)
- `enable_metrics`: Enable metrics (default: true)

**Fragments:**
- Write_files: systemd service, logrotate config
- Runcmd: Download script from GitHub, install, enable service

**Context-Aware**: Requires `deployment_id` and `app_name` from deployment context

#### RedisCapability
**Purpose**: Installs Redis server

**Fragments:**
- Packages: `redis-server`
- Runcmd: Enable and start service

#### PostgreSQLCapability
**Purpose**: Installs PostgreSQL database

**Configuration:**
- `version`: PostgreSQL version (14, 15)

**Fragments:**
- Packages: `postgresql-{version}`, `postgresql-client-{version}`
- Runcmd: Enable and start service

### Creating New Capabilities

**Steps:**

1. **Define capability class:**
```python
class MyCapability(Capability):
    def __init__(self, config_param: str = "default"):
        self.config_param = config_param
    
    def name(self) -> str:
        return "my-capability"
    
    def get_fragments(self) -> CapabilityFragments:
        fragments = CapabilityFragments()
        fragments.packages.append("my-package")
        fragments.runcmd.extend([
            "echo 'Setting up my capability'",
            "systemctl enable my-service",
        ])
        return fragments
```

2. **Register in _CAPABILITY_MAP:**
```python
_CAPABILITY_MAP = {
    # ... existing capabilities
    "my-capability": lambda config: MyCapability(
        config_param=config.get("config_param", "default")
    ),
}
```

3. **Use in templates:**
```yaml
capabilities:
  features:
    - my-capability
    # Or with config:
    - name: my-capability
      config:
        config_param: custom_value
```

---

## Deployment Flow

### Complete Deployment Sequence

```
┌─────────────────────────────────────────────────────────────┐
│ 1. USER PREPARES DEPLOYMENT                                 │
├─────────────────────────────────────────────────────────────┤
│ $ linode-cli build init llm-api                             │
│ $ cd llm-api                                                 │
│ $ cp .env.example .env                                       │
│ $ nano .env  # Configure environment variables              │
│ $ nano deploy.yml  # Customize if needed                    │
└─────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│ 2. DEPLOY COMMAND EXECUTION                                 │
├─────────────────────────────────────────────────────────────┤
│ $ linode-cli build deploy --wait                            │
│                                                              │
│ deploy.py:_cmd_deploy(args, config):                        │
│   a. Load deploy.yml from current directory                 │
│   b. Parse template data                                    │
│   c. Read .env file and merge with template env            │
│   d. Generate deployment_id (8-char unique ID)             │
│   e. Create capability manager with deployment context      │
│   f. Generate cloud-init configuration                      │
│   g. Call Linode API to create instance                     │
│   h. Save deployment metadata to registry                   │
│   i. Wait for instance to start (if --wait)                │
│   j. Perform health checks (if configured)                  │
└─────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│ 3. CAPABILITY MANAGER CREATION                              │
├─────────────────────────────────────────────────────────────┤
│ capabilities.create_capability_manager(                     │
│     template.data,                                          │
│     deployment_id="a3b7f9k2",                              │
│     app_name="llm-api"                                      │
│ )                                                            │
│                                                              │
│ → Parses capabilities section from template                 │
│ → Resolves runtime capability (docker)                      │
│ → Resolves feature capabilities (gpu-nvidia, buildwatch)    │
│ → Injects deployment context for context-aware capabilities │
│ → Returns CapabilityManager with all capabilities loaded    │
└─────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│ 4. CLOUD-INIT GENERATION                                    │
├─────────────────────────────────────────────────────────────┤
│ cloud_init.generate_cloud_init(config_obj)                  │
│                                                              │
│ config_obj contains:                                        │
│   - container_image, ports, env_vars                        │
│   - capability_manager (with all capabilities)              │
│   - custom_setup_script, custom_files, volumes             │
│                                                              │
│ → capability_manager.assemble_fragments()                   │
│   → Collects fragments from all capabilities                │
│   → Merges packages, runcmd, write_files, bootcmd          │
│                                                              │
│ → Generates cloud-init YAML with:                           │
│   - packages: from capabilities + system packages           │
│   - write_files: from capabilities + custom files          │
│   - bootcmd: early boot commands (GPU driver setup)        │
│   - runcmd: main setup commands                             │
│     1. Install packages                                     │
│     2. Setup capabilities (Docker, GPU, Redis, etc.)       │
│     3. Setup BuildWatch (if enabled)                       │
│     4. Run custom setup script (if provided)               │
│     5. Create systemd service for container                │
│     6. Start container with docker run                     │
│     7. Run post_start_script (if provided)                 │
│     8. Setup health check monitoring                       │
│                                                              │
│ → Returns cloud-init YAML as string                         │
└─────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│ 5. LINODE INSTANCE CREATION                                 │
├─────────────────────────────────────────────────────────────┤
│ client.call_operation('linodes', 'create', [                │
│     '--type', 'g6-standard-8',                              │
│     '--region', 'us-mia',                                   │
│     '--image', 'linode/ubuntu22.04',                        │
│     '--label', 'build-llm-api-default-11201430',           │
│     '--root_pass', '...',                                   │
│     '--metadata.user_data', '<base64-encoded-cloud-init>',  │
│     '--tags', 'build-id:a3b7f9k2',                         │
│     '--tags', 'build-app:llm-api',                         │
│     '--tags', 'build-env:default',                         │
│ ])                                                           │
│                                                              │
│ → Linode provisions instance                                │
│ → Cloud-init runs on first boot                            │
│ → Instance becomes available                                │
└─────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│ 6. METADATA TRACKING                                        │
├─────────────────────────────────────────────────────────────┤
│ DeploymentTracker.save_metadata(linode_id, metadata)       │
│   → Stores metadata in Linode instance metadata API        │
│                                                              │
│ registry.add_deployment(record)                             │
│   → Stores deployment in local registry                     │
│   → Location: ~/.config/linode-cli.d/build/registry.json   │
│                                                              │
│ Save .linode/state.json in deployment directory            │
│   → Tracks instance_id, deployment_id, app_name            │
│   → Used by TUI and status commands                        │
└─────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│ 7. INSTANCE INITIALIZATION (On Linode)                     │
├─────────────────────────────────────────────────────────────┤
│ Cloud-init executes on first boot:                          │
│                                                              │
│ bootcmd (early boot):                                        │
│   → Blacklist nouveau driver (for GPU)                      │
│   → Update initramfs                                        │
│                                                              │
│ packages:                                                    │
│   → apt-get install docker.io, nvidia packages, etc.       │
│                                                              │
│ write_files:                                                 │
│   → Create systemd services, config files                   │
│                                                              │
│ runcmd (main setup):                                         │
│   1. Install and configure Docker                           │
│   2. Install NVIDIA drivers (if GPU capability)            │
│   3. Setup BuildWatch monitoring (if enabled)              │
│   4. Create /app/docker-compose.yml                        │
│   5. Create systemd service for container                   │
│   6. Start container: docker run ...                        │
│   7. Wait for health check                                  │
│   8. Log success/failure                                    │
└─────────────────────────────────────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────────┐
│ 8. HEALTH CHECK & MONITORING                                │
├─────────────────────────────────────────────────────────────┤
│ If --wait flag used:                                        │
│   → Poll instance status until "running"                    │
│   → Perform health check (HTTP/TCP/exec)                   │
│   → Update deployment status in registry                    │
│                                                              │
│ BuildWatch (if enabled):                                    │
│   → Monitors Docker events                                  │
│   → Detects OOM kills, crash loops                         │
│   → Exposes API on port 9090                                │
│   → Provides /health, /status, /events, /issues endpoints  │
│                                                              │
│ User can check status:                                      │
│   $ linode-cli build status                                 │
│   $ linode-cli build tui                                    │
└─────────────────────────────────────────────────────────────┘
```

### Key Files During Deployment

**Input Files:**
- `deploy.yml`: Template configuration (in current directory)
- `.env`: Environment variables

**Generated Files:**
- `.linode/state.json`: Local deployment state
- `linode-root-password.txt`: Generated root password
- `connect.sh`: SSH helper script

**Remote Files (on Linode instance):**
- `/var/log/cloud-init-output.log`: Cloud-init execution log
- `/var/log/build-watcher/`: BuildWatch logs (if enabled)
- `/etc/systemd/system/app.service`: Container systemd service
- `/app/docker-compose.yml`: Container configuration

---

## Cloud-Init Generation

### CloudInitConfig Structure

```python
@dataclass
class CloudInitConfig:
    container_image: str
    internal_port: int
    external_port: int
    capability_manager: Optional[CapabilityManager]
    env_vars: Dict[str, str]
    post_start_script: Optional[str] = None
    command: Optional[str] = None
    custom_setup_script: Optional[str] = None
    custom_files: List[Dict[str, Any]] = None
    volumes: List[str] = None
```

### Generation Process

**Function**: `cloud_init.generate_cloud_init(config: CloudInitConfig) -> str`

**Steps:**

1. **Initialize base structure:**
   ```yaml
   #cloud-config
   package_update: true
   package_upgrade: false  # Don't auto-upgrade
   packages: []
   write_files: []
   bootcmd: []
   runcmd: []
   ```

2. **Add capability fragments:**
   ```python
   if config.capability_manager:
       fragments = config.capability_manager.assemble_fragments()
       cloud_config["packages"].extend(fragments.packages)
       cloud_config["bootcmd"].extend(fragments.bootcmd)
       cloud_config["runcmd"].extend(fragments.runcmd)
       cloud_config["write_files"].extend(fragments.write_files)
   ```

3. **Add container systemd service:**
   ```bash
   # /etc/systemd/system/app.service
   [Unit]
   Description=App Container
   After=docker.service
   Requires=docker.service
   
   [Service]
   Type=simple
   ExecStart=/usr/bin/docker run --name app --rm \
       -p {external_port}:{internal_port} \
       {env_vars} \
       {volumes} \
       {image} {command}
   Restart=always
   
   [Install]
   WantedBy=multi-user.target
   ```

4. **Add container start logic:**
   ```bash
   # runcmd:
   systemctl daemon-reload
   systemctl enable app
   systemctl start app
   sleep 5  # Wait for container to start
   ```

5. **Add health check (if configured):**
   ```bash
   # HTTP health check example:
   for i in {1..30}; do
       if curl -f http://localhost:8000/health; then
           echo "Health check passed"
           break
       fi
       echo "Waiting for service... ($i/30)"
       sleep 10
   done
   ```

6. **Add custom setup (if provided):**
   ```bash
   # Run custom setup script from template
   {custom_setup_script}
   ```

7. **Add post-start script (if provided):**
   ```bash
   # Run after container starts
   {post_start_script}
   ```

8. **Return YAML string:**
   ```python
   return yaml.dump(cloud_config, default_flow_style=False)
   ```

### Example Generated Cloud-Init

For a template with Docker + GPU + BuildWatch:

```yaml
#cloud-config
package_update: true
package_upgrade: false

packages:
  - docker.io
  - docker-compose
  - ubuntu-drivers-common

bootcmd:
  - echo 'blacklist nouveau' > /etc/modprobe.d/blacklist-nouveau.conf
  - update-initramfs -u || true

write_files:
  - path: /etc/systemd/system/build-watcher.service
    permissions: '0644'
    owner: root:root
    content: |
      [Unit]
      Description=BuildWatch
      After=network-online.target
      [Service]
      ExecStart=/usr/local/bin/build-watcher
      Environment="BUILD_DEPLOYMENT_ID=a3b7f9k2"
      Environment="BUILD_APP_NAME=llm-api"
      [Install]
      WantedBy=multi-user.target
  
  - path: /etc/systemd/system/app.service
    permissions: '0644'
    owner: root:root
    content: |
      [Unit]
      Description=App Container
      After=docker.service
      Requires=docker.service
      [Service]
      Type=simple
      ExecStart=/usr/bin/docker run --name app --rm \
        --gpus all \
        -p 80:8000 \
        -e MODEL_NAME=meta-llama/Meta-Llama-3-8B-Instruct \
        vllm/vllm-openai:latest
      Restart=always
      [Install]
      WantedBy=multi-user.target

runcmd:
  # Install Docker
  - systemctl enable docker
  - systemctl start docker
  
  # Install NVIDIA drivers
  - apt-get install -y nvidia-driver-535
  - modprobe nvidia
  - nvidia-smi
  
  # Install NVIDIA Container Toolkit
  - curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
  - apt-get update -qq
  - apt-get install -y nvidia-container-toolkit
  - nvidia-ctk runtime configure --runtime=docker
  - systemctl restart docker
  
  # Setup BuildWatch
  - mkdir -p /var/log/build-watcher
  - curl -fsSL https://raw.githubusercontent.com/.../build-watcher.py -o /usr/local/bin/build-watcher
  - chmod +x /usr/local/bin/build-watcher
  - systemctl daemon-reload
  - systemctl enable build-watcher
  - systemctl start build-watcher
  
  # Start application container
  - systemctl daemon-reload
  - systemctl enable app
  - systemctl start app
  - sleep 10
  
  # Health check
  - |
    for i in {1..60}; do
      if curl -f http://localhost:8000/health; then
        echo "✓ Service healthy"
        break
      fi
      echo "Waiting... ($i/60)"
      sleep 10
    done
```

---

## Key Components Deep Dive

### 1. Registry System (`registry.py`)

**Purpose**: Tracks all deployments locally

**Storage**: `~/.config/linode-cli.d/build/registry.json`

**Structure:**
```json
{
  "deployments": [
    {
      "deployment_id": "a3b7f9k2",
      "app_name": "llm-api",
      "env": "default",
      "template": "llm-api",
      "template_version": "0.1.0",
      "target": "linode",
      "region": "us-mia",
      "linode_type": "g6-standard-8",
      "linode_id": 12345678,
      "ipv4": "172.105.123.45",
      "hostname": "172-105-123-45.ip.linodeusercontent.com",
      "created_at": "2025-11-20T14:30:00Z",
      "last_status": "running"
    }
  ]
}
```

**Key Functions:**
- `add_deployment(record)`: Add new deployment
- `get_deployment(deployment_id)`: Get by ID
- `list_deployments()`: List all deployments
- `update_fields(deployment_id, fields)`: Update specific fields
- `remove_deployment(deployment_id)`: Remove from registry

### 2. Deployment Tracker (`deployment_tracker.py`)

**Purpose**: Store metadata on Linode instances

**Storage**: Linode instance metadata API

**Why?**: Registry is local only. Metadata API allows accessing deployment info from any machine via Linode API.

**Key Functions:**
- `save_metadata(linode_id, metadata)`: Store metadata on instance
- `get_metadata(linode_id)`: Retrieve metadata
- `find_by_deployment_id(deployment_id)`: Find instance by deployment ID

**Metadata Structure:**
```python
{
    "deployment_id": "a3b7f9k2",
    "app_name": "llm-api",
    "env": "default",
    "created_at": "2025-11-20T14:30:00Z",
    "created_from": "/path/to/deployment/dir",
    "health_config": {...},
    "hostname": "172-105-123-45.ip.linodeusercontent.com",
    "external_port": 80,
    "internal_port": 8000
}
```

### 3. Environment Variable System (`env.py`)

**Purpose**: Handle environment variable requirements and validation

**Key Classes:**
```python
@dataclass
class EnvRequirement:
    name: str
    description: str

def load_env_file(path: str) -> Dict[str, str]:
    """Load .env file into dict."""
    # Parses KEY=value format
    # Supports comments (#)
    # Handles quoted values

def ensure_required(env_values: Dict[str, str], requirements: List[EnvRequirement]):
    """Validate required env vars are present."""
    # Raises EnvError if missing required vars
```

**Usage in Templates:**
```yaml
env:
  required:
    - name: API_KEY
      description: Your API key from dashboard
  optional:
    - name: MODEL_NAME
      description: Model to use (default: llama-3)
```

**Deployment Flow:**
1. Template declares required/optional env vars
2. User creates .env file
3. deploy.py loads and validates .env
4. Env vars merged with template defaults
5. Passed to container via -e flags

### 4. BuildWatch System (`build_watcher.py` + `BuildWatchCapability`)

**Purpose**: Monitor Docker containers and detect issues

**Architecture:**
- **Daemon**: Python script runs as systemd service
- **Events**: Monitors Docker daemon events in real-time
- **API**: HTTP server on port 9090
- **Storage**: Issues and events stored in memory + log files

**Capability Integration:**
```python
class BuildWatchCapability(Capability):
    def __init__(self, deployment_id, app_name, port=9090, 
                 log_retention_days=7, enable_metrics=True):
        # Validates inputs
        # Stores configuration
    
    def get_fragments(self):
        # Returns:
        # - systemd service file
        # - logrotate config
        # - runcmd to download and install script
```

**API Endpoints:**
- `GET /health`: Service health
- `GET /status`: Deployment status
- `GET /events`: Recent Docker events
- `GET /issues`: Detected issues (OOM, crashes, etc.)

**Issue Detection:**
- OOM kills (out of memory)
- Crash loops (repeated restarts)
- Container exits with non-zero codes
- Long startup times

### 5. TUI System (`tui/`)

**Framework**: Textual (Python TUI framework)

**Architecture:**
```
tui/
├── app.py              # Main TUI application
├── api.py              # API wrapper for Linode + registry
├── utils.py            # Utilities
├── styles.tcss         # CSS-like styles
├── screens/
│   ├── home.py        # Deployment list/dashboard
│   ├── status.py      # Deployment detail view
│   ├── logs.py        # Log viewer
│   └── ...
└── widgets/
    ├── deployment_card.py
    ├── status_indicator.py
    └── ...
```

**Key Features:**
- Real-time deployment monitoring
- Log streaming
- Health check visualization
- Instance control (view, destroy)
- Keyboard navigation

**Data Flow:**
```
TUI → api.py → registry.py / Linode API → Display in UI
```

---

## Extension Points

### Adding New Commands

**Steps:**

1. **Create command module** (`linodecli_build/commands/mycommand.py`):
```python
def register(subparsers, config):
    parser = subparsers.add_parser("mycommand", help="My command")
    parser.add_argument("--option", help="An option")
    parser.set_defaults(func=lambda args: _cmd_mycommand(args, config))

def _cmd_mycommand(args, config):
    print("Executing my command")
    # Command logic here
```

2. **Register in `__init__.py`**:
```python
# commands/__init__.py
from . import mycommand

def register_commands(subparsers, config):
    # ... existing commands
    mycommand.register(subparsers, config)
```

### Adding New Capabilities

See "Creating New Capabilities" section above. Key points:
1. Extend `Capability` base class
2. Implement `name()` and `get_fragments()`
3. Register in `_CAPABILITY_MAP`

### Adding New Template Fields

**Steps:**

1. **Update template YAML schema** (documentation)
2. **Parse in `deploy.py`**:
```python
my_field = template.data.get("my_field")
```
3. **Use in cloud-init generation** or pass to capability manager
4. **Update validation** (if adding required field)

### Integrating New Cloud Providers

Currently Linode-only, but designed for extension:

**Steps:**

1. **Create provider module** (`linodecli_build/providers/aws.py`)
2. **Implement provider interface**:
```python
class AWSProvider:
    def create_instance(self, config):
        # AWS-specific creation
        pass
    
    def get_instance(self, instance_id):
        # AWS-specific retrieval
        pass
```
3. **Update deploy.py to support multiple targets**:
```python
target = template.data.get("deploy", {}).get("target")
if target == "linode":
    # Linode flow
elif target == "aws":
    # AWS flow
```

---

## Data Flow Diagrams

### Deployment Creation Flow

```
User Input                Template System         Capability System        Linode API
─────────────────────────────────────────────────────────────────────────────────────
    │
    │ linode-cli build init llm-api
    ├─────────────────────► Load template
    │                       Create deploy.yml
    │                       Create .env.example
    │◄─────────────────────
    │
    │ Edit deploy.yml & .env
    │
    │ linode-cli build deploy --wait
    ├─────────────────────► Parse deploy.yml
    │                       Read .env
    │                       Generate deployment_id
    │                           │
    │                           │ create_capability_manager()
    │                           ├──────────────────► Parse capabilities
    │                           │                    Load from registry
    │                           │                    Inject context
    │                           │◄──────────────────
    │                           │
    │                           │ generate_cloud_init()
    │                           ├──────────────────► assemble_fragments()
    │                           │                    Combine all fragments
    │                           │                    Generate YAML
    │                           │◄──────────────────
    │                           │
    │                           │ client.call_operation('linodes', 'create')
    │                           ├──────────────────────────────────────► Create instance
    │                           │                                        Run cloud-init
    │                           │◄──────────────────────────────────────
    │                           │
    │                       Save to registry
    │                       Save metadata
    │◄─────────────────────
    │
    │ Instance running with:
    │ - Docker installed
    │ - GPU drivers (if requested)
    │ - BuildWatch (if requested)
    │ - Container running
    │ - Health checks passing
```

### Capability Fragment Assembly

```
Template YAML                CapabilityManager              Capabilities
────────────────────────────────────────────────────────────────────────
capabilities:
  runtime: docker      ──► add_from_config()
  features:                     │
    - gpu-nvidia        ───────► add_capability("docker")
    - buildwatch        ───────► add_capability("gpu-nvidia") ──► GPUNvidiaCapability
                        ───────► add_capability("buildwatch")     │ get_fragments()
                                     │                         │   │
                                     │                         │   ├─► packages: [ubuntu-drivers-common]
                                     │                         │   ├─► bootcmd: [blacklist nouveau]
                                     │                         │   └─► runcmd: [install drivers]
                                     │                         │
                                     │                         ├──► BuildWatchCapability
                                     │                              │ get_fragments()
                                     │                              │
                                     │                              ├─► write_files: [systemd service]
                                     │                              └─► runcmd: [install BuildWatch]
                                     │
                                     ▼
                            assemble_fragments()
                                     │
                                     ├─► Combine all packages
                                     ├─► Combine all bootcmd
                                     ├─► Combine all runcmd
                                     ├─► Combine all write_files
                                     │
                                     ▼
                            Return CapabilityFragments
                                     │
                                     ▼
                            Used by generate_cloud_init()
```

---

## Important Design Patterns

### 1. Declarative Configuration

Users declare **what** they want (GPU, Docker, Redis), not **how** to set it up.

**Benefit**: Reduces complexity, improves maintainability, enables LLM-assisted template creation.

### 2. Composable Capabilities

Capabilities can be mixed and matched freely.

**Example**: `docker` + `gpu-nvidia` + `redis` + `buildwatch` all work together.

### 3. Context Injection

Some capabilities need deployment context (deployment_id, app_name). The system injects this automatically.

**Example**: BuildWatch needs deployment_id to tag logs and events.

### 4. Fragment Assembly

Each capability returns fragments independently. The system assembles them in the correct order.

**Order**:
1. bootcmd (early boot)
2. packages (install)
3. write_files (config files)
4. runcmd (setup and start services)

### 5. Separation of Concerns

- **Templates**: Define application requirements
- **Capabilities**: Define infrastructure setup
- **Cloud-init**: Handles provisioning
- **Registry**: Tracks deployments
- **TUI**: Provides monitoring

### 6. Local-first with Cloud Sync

Deployments tracked locally (registry.json) AND remotely (Linode metadata API).

**Benefit**: Works offline for local operations, syncs state to cloud for multi-machine access.

---

## Common Workflows

### Workflow 1: Deploy from Bundled Template

```bash
# 1. Initialize from template
linode-cli build init llm-api

# 2. Configure
cd llm-api
cp .env.example .env
nano .env  # Add HF_TOKEN, etc.

# 3. Optional: Customize deploy.yml
nano deploy.yml

# 4. Deploy
linode-cli build deploy --wait

# 5. Monitor
linode-cli build status
linode-cli build tui
```

### Workflow 2: Create Custom Template

```bash
# 1. Scaffold with LLM assistance
linode-cli build templates scaffold my-api --llm-assist

# 2. Complete template (manually or with LLM)
cd my-api
# Edit template.yml

# 3. Validate
linode-cli build templates validate .

# 4. Test deployment
linode-cli build init ./my-api --directory test
cd test
linode-cli build deploy --wait

# 5. Install for reuse
linode-cli build templates install ../my-api

# 6. Use like bundled template
linode-cli build init my-api --directory production
```

### Workflow 3: Debug Failed Deployment

```bash
# 1. Check status
linode-cli build status <deployment-id>

# 2. SSH into instance
./connect.sh  # Created during deployment

# 3. Check cloud-init logs
cat /var/log/cloud-init-output.log

# 4. Check container status
docker ps -a
docker logs app

# 5. Check BuildWatch (if enabled)
curl http://localhost:9090/issues

# 6. Check systemd services
systemctl status app
systemctl status build-watcher

# 7. Manual fixes, then redeploy if needed
# Exit SSH
linode-cli build destroy <deployment-id>
linode-cli build deploy --wait
```

---

## Configuration Files

### Registry (`~/.config/linode-cli.d/build/registry.json`)

```json
{
  "deployments": [
    {
      "deployment_id": "a3b7f9k2",
      "app_name": "llm-api",
      "env": "default",
      "template": "llm-api",
      "template_version": "0.1.0",
      "target": "linode",
      "region": "us-mia",
      "linode_type": "g6-standard-8",
      "linode_id": 12345678,
      "ipv4": "172.105.123.45",
      "hostname": "172-105-123-45.ip.linodeusercontent.com",
      "health": {
        "type": "http",
        "path": "/health",
        "port": 8000
      },
      "external_port": 80,
      "internal_port": 8000,
      "created_at": "2025-11-20T14:30:00Z",
      "last_status": "running"
    }
  ]
}
```

### Local State (`.linode/state.json`)

```json
{
  "instance_id": 12345678,
  "app_name": "llm-api",
  "environment": "default",
  "deployment_id": "a3b7f9k2",
  "created": "2025-11-20T14:30:00Z",
  "ipv4": "172.105.123.45",
  "hostname": "172-105-123-45.ip.linodeusercontent.com",
  "region": "us-mia",
  "linode_type": "g6-standard-8"
}
```

### User Templates Index (`~/.config/linode-cli.d/build/templates/index.yml`)

```yaml
templates:
  - name: my-custom-template
    path: /home/user/.config/linode-cli.d/build/templates/my-custom-template/template.yml
    source: user
```

---

## Best Practices for LLM Agents

### When Modifying Code

1. **Understand capability flow**: Templates → CapabilityManager → Fragments → Cloud-init
2. **Maintain fragment structure**: Always return proper CapabilityFragments
3. **Validate YAML**: Use `yaml.safe_load()` to verify template syntax
4. **Test capabilities independently**: Each capability should work standalone
5. **Preserve deployment context**: Don't break deployment_id/app_name injection

### When Creating Templates

1. **Use capabilities over custom scripts**: Prefer declarative capabilities
2. **Set appropriate timeouts**: GPU models need 180+ seconds for initial_delay
3. **Include health checks**: Always define health check configuration
4. **Document env vars**: Clear descriptions with examples
5. **Test before publishing**: Use `templates validate` and test deployments

### When Adding Features

1. **Follow existing patterns**: See how similar features are implemented
2. **Update documentation**: Keep docs in sync with code
3. **Consider backwards compatibility**: Don't break existing templates
4. **Add validation**: Validate inputs early with clear error messages
5. **Test thoroughly**: Unit tests + integration tests + manual testing

---

## Troubleshooting Guide

### Common Issues

**Issue**: Template validation fails
- **Check**: Required fields (name, version, description, deploy)
- **Check**: Capability names are valid
- **Check**: YAML syntax is correct

**Issue**: Deployment fails during cloud-init
- **Check**: `/var/log/cloud-init-output.log` on instance
- **Check**: Capability compatibility (GPU requires Ubuntu 22.04)
- **Check**: Container image is accessible

**Issue**: Container won't start
- **Check**: `docker logs app`
- **Check**: Environment variables are correct
- **Check**: Ports aren't conflicting

**Issue**: Health check fails
- **Check**: `initial_delay_seconds` is long enough
- **Check**: Path and port are correct
- **Check**: Container is actually healthy

**Issue**: GPU not available in container
- **Check**: Used `gpu-nvidia` capability
- **Check**: Used `--gpus all` in docker run
- **Check**: nvidia-smi works on host

---

## Summary

This system provides a **declarative, template-driven approach** to deploying AI/ML workloads on Linode. Key principles:

1. **Declarative over Imperative**: Declare what you want, not how to set it up
2. **Composable Capabilities**: Mix and match infrastructure components
3. **Template-Driven**: Reusable deployment patterns
4. **Cloud-Init Based**: Standard provisioning mechanism
5. **Tracked Deployments**: Local registry + cloud metadata
6. **Monitoring Built-In**: Optional BuildWatch for container monitoring

The architecture is designed for **extensibility** (new capabilities, commands, providers) and **maintainability** (clear separation of concerns, well-defined interfaces).

---

## Quick Reference

### Key Files to Understand

1. `linodecli_build/commands/deploy.py` - Main deployment logic
2. `linodecli_build/core/capabilities.py` - Capability system
3. `linodecli_build/core/cloud_init.py` - Cloud-init generation
4. `linodecli_build/core/templates.py` - Template loading
5. `linodecli_build/core/registry.py` - Deployment tracking

### Key Concepts

- **Template**: YAML definition of deployment
- **Capability**: Infrastructure component (Docker, GPU, Redis, etc.)
- **Fragments**: Cloud-init components (packages, runcmd, etc.)
- **Deployment ID**: Unique 8-char identifier for each deployment
- **Cloud-init**: Standard cloud instance initialization system

### Command Cheat Sheet

```bash
# Deploy from template
linode-cli build init <template>
linode-cli build deploy --wait

# Manage templates
linode-cli build templates list
linode-cli build templates validate <path>
linode-cli build templates scaffold <name> --llm-assist

# Monitor deployments
linode-cli build status [deployment-id]
linode-cli build tui

# Clean up
linode-cli build destroy [deployment-id]
```

---

**Last Updated**: 2025-11-20
**Version**: 2.0 (with BuildWatch as optional capability)
