# Capabilities Reference

## Overview

**Capabilities** are declarative infrastructure components that templates use to specify what they need. Instead of writing shell scripts, you simply declare capabilities like `gpu-nvidia`, `redis`, or `buildwatch`, and the system handles the installation and configuration automatically.

## How Capabilities Work

Capabilities are declared in the `capabilities` section of your template:

```yaml
capabilities:
  runtime: docker          # Base runtime environment
  features:                # Additional features to install
    - gpu-nvidia
    - redis
    - buildwatch
  packages:                # Custom apt packages
    - ffmpeg
    - libopencv-dev
```

When you deploy, the system:
1. Parses your capability declarations
2. Generates installation scripts for each capability
3. Combines them into a cloud-init configuration
4. Provisions your Linode instance with everything installed

**Benefits:**
- ✅ **Declarative** - Say what you need, not how to install it
- ✅ **Composable** - Mix and match capabilities freely
- ✅ **Tested** - Each capability is proven and reliable
- ✅ **Maintainable** - No custom shell scripts to debug

---

## Runtime Capabilities

The `runtime` specifies the base environment for your application.

### Docker Runtime

**Name:** `docker`

**Purpose:** Installs Docker and Docker Compose for containerized applications.

**Configuration:**
```yaml
capabilities:
  runtime: docker
```

**What it installs:**
- `docker.io` - Docker engine
- `docker-compose` - Docker Compose tool

**What it does:**
- Enables and starts the Docker service
- Configures Docker to start on boot

**When to use:**
- Running containerized applications (most common)
- Using Docker images from registries
- Need container isolation and portability

---

### Native Runtime

**Name:** `native`

**Purpose:** No containerization - runs applications directly on the host OS.

**Configuration:**
```yaml
capabilities:
  runtime: native
```

**What it does:**
- Nothing - this is a no-op runtime
- You handle application installation via custom scripts or other capabilities

**When to use:**
- Running native binaries
- Maximum performance (no container overhead)
- Legacy applications that don't work in containers

---

## Feature Capabilities

Features are additional components you can add to your deployment.

### GPU Support (NVIDIA)

**Name:** `gpu-nvidia`

**Purpose:** Installs NVIDIA GPU drivers and container toolkit for GPU-accelerated workloads.

**Configuration:**
```yaml
capabilities:
  runtime: docker
  features:
    - gpu-nvidia
```

**What it installs:**
- NVIDIA drivers (version 535 - proven stable)
- `nvidia-container-toolkit` - GPU support in Docker
- Required kernel modules

**What it does:**
- Blacklists nouveau driver (conflicts with NVIDIA)
- Installs and configures NVIDIA drivers
- Configures Docker to use GPU runtime
- Verifies installation with `nvidia-smi`

**Requirements:**
- ⚠️ **Must use Ubuntu 22.04** (`linode/ubuntu22.04`)
- ⚠️ **Must use GPU instance type** (e.g., `g6-standard-8`)

**Container usage:**
```yaml
container:
  image: pytorch/pytorch:2.0-cuda11.7
  # GPU is automatically available via --gpus all flag
```

**Verification:**
```bash
# SSH to instance
nvidia-smi  # Should show GPU info

# In container
docker exec app nvidia-smi
```

**When to use:**
- LLM inference (vLLM, Ollama, etc.)
- ML training or fine-tuning
- Computer vision workloads
- Any CUDA-accelerated applications

**Troubleshooting:**
- If `nvidia-smi` fails, check `/var/log/cloud-init-output.log`
- Ensure you're using Ubuntu 22.04 (24.04 has driver issues)
- GPU instances can take 3-5 minutes for driver installation

---

### Docker Optimization

**Name:** `docker-optimize`

**Purpose:** Enables parallel layer downloads for faster image pulls.

**Configuration:**
```yaml
capabilities:
  features:
    - docker-optimize
```

**What it does:**
- Configures Docker daemon for 10 concurrent downloads
- Creates `/etc/docker/daemon.json` with optimization settings

**Effect:**
Large Docker images (like vLLM or PyTorch) download significantly faster.

**When to use:**
- Large container images (>1GB)
- GPU workloads with big base images
- Any deployment where startup time matters

**Note:** This is particularly useful for AI/ML images which are often 5-10GB.

---

### Redis

**Name:** `redis`

**Purpose:** Installs and configures Redis server for caching and data storage.

**Configuration:**
```yaml
capabilities:
  features:
    - redis
```

**What it installs:**
- `redis-server` - Redis database

**What it does:**
- Installs Redis
- Enables and starts the service
- Configures to start on boot

**Default configuration:**
- Port: 6379
- Bind: localhost (not exposed externally)
- No password (add via custom setup if needed)

**Usage in your application:**
```yaml
container:
  env:
    REDIS_URL: redis://localhost:6379
```

**When to use:**
- Caching API responses
- Session storage
- Rate limiting
- Job queues
- Real-time analytics

**Accessing from your container:**
```python
import redis
client = redis.Redis(host='host.docker.internal', port=6379)
# Note: Use host.docker.internal to access host Redis from container
```

---

### PostgreSQL

**Name:** `postgresql-14`, `postgresql-15`

**Purpose:** Installs PostgreSQL database server.

**Configuration:**
```yaml
capabilities:
  features:
    - postgresql-14  # or postgresql-15
```

**What it installs:**
- `postgresql-{version}` - PostgreSQL server
- `postgresql-client-{version}` - PostgreSQL client tools

**What it does:**
- Installs PostgreSQL
- Enables and starts the service
- Configures to start on boot

**Default configuration:**
- Port: 5432
- User: postgres
- Database: postgres

**Usage in your application:**
```yaml
container:
  env:
    DATABASE_URL: postgresql://postgres@host.docker.internal:5432/mydb
```

**Post-deployment setup:**
```bash
# SSH to instance
sudo -u postgres psql

# Create database and user
CREATE DATABASE myapp;
CREATE USER myapp_user WITH PASSWORD 'secure_password';
GRANT ALL PRIVILEGES ON DATABASE myapp TO myapp_user;
```

**When to use:**
- Persistent data storage
- Relational data with ACID guarantees
- Complex queries and joins
- Production applications

---

### Python Runtime

**Name:** `python-3.10`, `python-3.11`, `python-3.12`

**Purpose:** Installs specific Python version for native applications.

**Configuration:**
```yaml
capabilities:
  runtime: native
  features:
    - python-3.11
```

**What it installs:**
- `python{version}` - Python interpreter
- `python{version}-venv` - Virtual environment support
- `python{version}-dev` - Development headers
- `python3-pip` - Package installer

**What it does:**
- Adds deadsnakes PPA (for latest Python versions)
- Installs Python and development tools

**When to use:**
- Native Python applications (not containerized)
- Need specific Python version
- Building Python packages from source

**Note:** For containerized apps, use a Python base image instead.

---

### Node.js Runtime

**Name:** `nodejs-18`, `nodejs-20`

**Purpose:** Installs Node.js for JavaScript applications.

**Configuration:**
```yaml
capabilities:
  runtime: native
  features:
    - nodejs-20
```

**What it installs:**
- `nodejs` - Node.js runtime
- `npm` - Node package manager

**What it does:**
- Adds NodeSource repository
- Installs Node.js

**When to use:**
- Native Node.js applications
- Need specific Node.js version
- Building frontend applications

**Note:** For containerized apps, use a Node.js base image instead.

---

### BuildWatch (Container Monitoring)

**Name:** `buildwatch`

**Purpose:** Real-time Docker container monitoring with automatic issue detection.

**Status:** ⚠️ **Optional** - Must be explicitly added to templates

**Configuration:**

Simple (use defaults):
```yaml
capabilities:
  runtime: docker
  features:
    - buildwatch
```

Advanced (with custom config):
```yaml
capabilities:
  runtime: docker
  features:
    - name: buildwatch
      config:
        port: 9090              # HTTP API port (default: 9090)
        log_retention_days: 7   # Log rotation (default: 7)
        enable_metrics: true    # Resource metrics (default: true)
```

**What it does:**
- Installs BuildWatch monitoring service
- Monitors all Docker containers in real-time
- Detects issues automatically (OOM kills, crash loops)
- Provides HTTP API for status and events
- Logs events and metrics

**Features:**
- ✅ Real-time Docker event streaming
- ✅ Automatic issue detection
- ✅ HTTP API on port 9090
- ✅ Container lifecycle tracking
- ✅ Resource metrics collection
- ✅ Persistent logs (7-day rotation)

**When to use:**
- GPU workloads (detect OOM issues)
- Production deployments (issue alerting)
- Long-running services (uptime tracking)
- Development (debugging container issues)

**When to skip:**
- Simple test deployments
- Minimal resource usage requirements
- No container monitoring needed

### Using BuildWatch

#### 1. TUI Dashboard (Recommended)

```bash
linode-cli build tui
```

**What you see:**
- Real-time container events (updated every 5 seconds)
- Color-coded event types:
  - 🟢 Green: Container starts
  - 🔴 Red: Container crashes/dies
  - 🟡 Yellow: Container stops
  - 🔵 Cyan: Container restarts
- Detected issues with severity levels
- Actionable recommendations

#### 2. CLI Status Command

```bash
# Basic status
linode-cli build status

# Detailed with BuildWatch info
linode-cli build status --verbose
```

**Verbose output includes:**
```
BuildWatch Status:
  Recent Events:
    [19:00:15] ✓ app started
    [19:02:30] ✕ app died (exit code: 137)
    [19:02:35] ↻ app restarted

  Issues Detected:
    ✕ CRITICAL: Container killed due to out of memory
      → Increase memory limit or optimize application
```

#### 3. HTTP API

BuildWatch exposes an HTTP API on port 9090:

**Get Recent Events:**
```bash
curl http://<instance-ip>:9090/events?limit=50
```

Response:
```json
{
  "events": [
    {
      "timestamp": "2025-11-20T19:00:00Z",
      "type": "start",
      "container": "app",
      "image": "my-app:latest",
      "id": "a1b2c3d4e5f6"
    },
    {
      "timestamp": "2025-11-20T19:02:15Z",
      "type": "die",
      "container": "app",
      "exit_code": 137,
      "id": "a1b2c3d4e5f6"
    }
  ],
  "count": 2
}
```

**Get Detected Issues:**
```bash
curl http://<instance-ip>:9090/issues
```

Response:
```json
{
  "issues": [
    {
      "timestamp": "2025-11-20T19:02:15Z",
      "severity": "critical",
      "type": "oom_killed",
      "container": "app",
      "message": "Container killed - likely out of memory",
      "recommendation": "Increase memory limit or optimize application",
      "resolved": false
    }
  ],
  "count": 1
}
```

**API Endpoints:**

| Endpoint | Description |
|----------|-------------|
| `/health` | Service health check |
| `/status` | Full deployment state |
| `/events?limit=N` | Recent container events |
| `/issues` | Detected problems |
| `/logs?container=X&lines=N` | Container logs |

#### 4. Log Files on Instance

```
/var/log/build-watcher/
├── events.log      # Container lifecycle events (JSON lines)
├── status.log      # Periodic status snapshots (every 5 min)
├── metrics.log     # System metrics (every 1 min)
└── errors.log      # Detected issues and errors
```

**Accessing logs via SSH:**
```bash
# SSH to your instance
ssh root@<instance-ip>

# View recent events
tail -f /var/log/build-watcher/events.log

# View detected issues
tail -f /var/log/build-watcher/errors.log

# Check service status
systemctl status build-watcher
```

### Issue Detection

BuildWatch automatically detects common problems:

**🔴 OOM Kills (Out of Memory)**
- **Detection:** Exit code 137 (SIGKILL)
- **Severity:** Critical
- **Recommendation:** Increase memory limit or optimize application

**🟡 Frequent Restarts**
- **Detection:** 3+ restarts within 5 minutes
- **Severity:** Warning
- **Recommendation:** Check application logs for crash cause

**🟡 Health Check Failures**
- **Detection:** Container health status becomes unhealthy
- **Severity:** Warning
- **Recommendation:** Verify application health endpoint

### BuildWatch Troubleshooting

**Service Not Running:**
```bash
# Check service status
systemctl status build-watcher

# View service logs
journalctl -u build-watcher -f

# Restart service
systemctl restart build-watcher
```

**API Not Responding:**
```bash
# Check if port 9090 is open
netstat -tulpn | grep 9090

# Test locally on instance
curl http://localhost:9090/health
```

**Missing Events:**
```bash
# Check Docker is running
docker ps

# Check build-watcher can access Docker
docker events  # Should show real-time events
```

---

## Custom Packages

Install any additional system packages your application needs.

**Configuration:**
```yaml
capabilities:
  packages:
    - ffmpeg              # Media processing
    - libopencv-dev       # Computer vision
    - build-essential     # Compilation tools
    - libcurl4            # HTTP client library
```

**What it does:**
- Runs `apt-get install` for each package
- Packages installed before your application starts

**When to use:**
- Application requires system libraries
- Need build tools for compilation
- Specific codec or utility needed

**Note:** Packages must be available in Ubuntu apt repositories.

---

## Capability Combinations

Capabilities can be mixed and matched. Here are common combinations:

### GPU Workload with Monitoring

```yaml
capabilities:
  runtime: docker
  features:
    - gpu-nvidia
    - docker-optimize
    - buildwatch
```

**Use case:** LLM inference, ML training

---

### Full Stack Application

```yaml
capabilities:
  runtime: docker
  features:
    - redis
    - postgresql-14
    - buildwatch
```

**Use case:** Web application with database and cache

---

### ML Pipeline with Storage

```yaml
capabilities:
  runtime: docker
  features:
    - gpu-nvidia
    - docker-optimize
    - redis
    - buildwatch
  packages:
    - ffmpeg
    - libopencv-dev
```

**Use case:** Video processing or computer vision pipeline

---

### Native Python Application

```yaml
capabilities:
  runtime: native
  features:
    - python-3.11
    - redis
  packages:
    - build-essential
    - libpq-dev
```

**Use case:** Python service with Redis, no containerization

---

## Configuration Examples

### Minimal (Docker Only)

```yaml
name: simple-app
display_name: Simple App
version: 1.0.0

capabilities:
  runtime: docker

deploy:
  target: linode
  linode:
    image: linode/ubuntu24.04
    region_default: us-ord
    type_default: g6-standard-2
    
    container:
      image: nginx:latest
      internal_port: 80
      external_port: 80
```

---

### GPU with Monitoring

```yaml
name: llm-api
display_name: LLM API
version: 1.0.0

capabilities:
  runtime: docker
  features:
    - gpu-nvidia
    - docker-optimize
    - buildwatch

deploy:
  target: linode
  linode:
    image: linode/ubuntu22.04      # Required for GPU
    region_default: us-mia
    type_default: g6-standard-8     # GPU instance
    
    container:
      image: vllm/vllm-openai:latest
      internal_port: 8000
      external_port: 80
```

---

### Full Stack with Database

```yaml
name: webapp
display_name: Web Application
version: 1.0.0

capabilities:
  runtime: docker
  features:
    - redis
    - postgresql-14
    - buildwatch

deploy:
  target: linode
  linode:
    image: linode/ubuntu24.04
    region_default: us-east
    type_default: g6-standard-4
    
    container:
      image: myapp:latest
      internal_port: 3000
      external_port: 80
      env:
        REDIS_URL: redis://host.docker.internal:6379
        DATABASE_URL: postgresql://postgres@host.docker.internal:5432/myapp
```

---

## Best Practices

### 1. Choose the Right Runtime

- **Use `docker`** for most applications (isolation, portability)
- **Use `native`** only for performance-critical apps or when containers aren't an option

### 2. GPU Workloads

- ✅ **Always use Ubuntu 22.04** for GPU instances
- ✅ **Include `docker-optimize`** for faster image pulls
- ✅ **Include `buildwatch`** to detect OOM issues
- ✅ **Set generous health check timeouts** (3+ minutes for model loading)

### 3. Database Considerations

- **Redis** and **PostgreSQL** are installed on the host, not in containers
- Access from containers using `host.docker.internal`
- Consider using managed databases for production (Linode Databases)

### 4. Monitoring

- **Include `buildwatch`** for production deployments
- **Skip `buildwatch`** for simple tests or minimal deployments
- BuildWatch helps debug issues quickly (OOM kills, crash loops)

### 5. Custom Packages

- Only add packages your application actually needs
- Test packages are available in Ubuntu repos
- Consider using Docker images with packages pre-installed instead

---

## Validation

Templates are validated automatically when you deploy. Common issues:

**Invalid capability name:**
```
Error: Unknown capability: gpu-nvida
Did you mean: gpu-nvidia?
```

**Missing runtime:**
```
Error: Runtime must be specified in capabilities
```

**GPU without Ubuntu 22.04:**
```
Warning: GPU capability requires Ubuntu 22.04
Current image: linode/ubuntu24.04
```

**Conflicting capabilities:**
```
Error: Capability gpu-nvidia conflicts with gpu-amd
```

---

## Extending Capabilities

Want to add a new capability? See [Template Development Guide](template-development.md) for instructions on creating custom capabilities.

**Common reasons to create custom capabilities:**
- Installing specialized software (Kubernetes, Nomad, etc.)
- Configuring specific services
- Setting up monitoring tools
- Custom security configurations

---

## Summary

**Capabilities make infrastructure declarative:**

1. ✅ **Declare what you need** - No shell scripts to write
2. ✅ **Compose capabilities freely** - Mix and match as needed
3. ✅ **Tested and reliable** - Each capability is proven
4. ✅ **Easy to maintain** - Clear, readable template files

**Available capabilities:**

| Category | Capabilities |
|----------|-------------|
| **Runtime** | `docker`, `native` |
| **GPU** | `gpu-nvidia` |
| **Databases** | `redis`, `postgresql-14`, `postgresql-15` |
| **Languages** | `python-3.10`, `python-3.11`, `python-3.12`, `nodejs-18`, `nodejs-20` |
| **Optimization** | `docker-optimize` |
| **Monitoring** | `buildwatch` (optional) |
| **Custom** | Any apt package via `packages` |

**Quick reference:**
```yaml
capabilities:
  runtime: docker
  features:
    - gpu-nvidia          # NVIDIA GPU
    - docker-optimize     # Fast image pulls
    - redis               # Redis cache
    - postgresql-14       # PostgreSQL DB
    - buildwatch          # Container monitoring
  packages:
    - ffmpeg              # Custom packages
```

---

## Further Reading

- **[Template Development Guide](template-development.md)** - Create templates using capabilities
- **[Template Quick Reference](template-quick-reference.md)** - Quick capability examples
- **[Template Deployments](template-deployments.md)** - Deployment workflows

---

**Questions?** [Open an issue](https://github.com/linode/linode-cli-ai/issues) or check our [Community Forum](https://www.linode.com/community/).
