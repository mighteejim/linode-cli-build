# User Guide

Complete guide to deploying and managing applications with `linode-cli build`.

## Table of Contents

1. [Quick Start](#quick-start)
2. [Template Commands](#template-commands)
3. [Deployment Workflow](#deployment-workflow)
4. [Configuration](#configuration)
5. [BuildWatch Monitoring](#buildwatch-monitoring)
6. [Multiple Environments](#multiple-environments)

---

## Quick Start

Deploy an AI service in under 2 minutes:

```bash
# 1. Initialize from template
linode-cli build init llm-api --directory my-llm
cd my-llm

# 2. Configure (optional)
nano deploy.yml  # Customize region, instance type, etc.
cp .env.example .env  # Set your environment variables

# 3. Deploy!
linode-cli build deploy --wait

# 4. Check status
linode-cli build status
```

That's it! Your service is now running on Linode.

---

## Template Commands

### List Available Templates

```bash
linode-cli build templates list
```

Shows bundled and user-installed templates.

### Show Template Details

```bash
linode-cli build templates show <name>
```

View template configuration, requirements, and usage.

### Scaffold a New Template

Create templates with AI assistance:

```bash
linode-cli build templates scaffold my-api --llm-assist
```

Or interactively:

```bash
linode-cli build templates scaffold my-api
```

### Validate a Template

Check template for errors:

```bash
linode-cli build templates validate <path>
```

Examples:
```bash
linode-cli build templates validate my-template/
linode-cli build templates validate my-template/template.yml
```

### Install/Uninstall Templates

```bash
# Install for reuse
linode-cli build templates install ./my-template

# Remove installed template
linode-cli build templates uninstall my-template
```

Installed templates are stored at `~/.config/linode-cli.d/build/templates/`.

---

## Deployment Workflow

Every deployment created via `linode-cli build init` contains:

```
my-deployment/
├── deploy.yml        # Complete deployment config
├── .env              # Your secrets
├── .env.example      # Template
└── README.md         # Usage instructions
```

### 1. Initialize

```bash
linode-cli build init chat-agent --directory chat-demo
cd chat-demo
```

### 2. Review and Customize

```bash
# Review settings
cat deploy.yml

# Optional: customize region, instance type, etc.
nano deploy.yml

# Configure environment variables
cp .env.example .env
nano .env  # Fill in required values
```

### 3. Deploy

```bash
linode-cli build deploy --wait
```

Without `--wait`, deployment happens in the background. Use `status` to check progress.

### 4. Check Status

```bash
linode-cli build status
```

Shows all deployments, their health, and connection info.

### 5. Destroy When Finished

```bash
linode-cli build destroy
```

Tears down the Linode instance and removes tracking data.

---

## Configuration

### deploy.yml Structure

When you run `init`, the template is copied to `deploy.yml` in your deployment directory. You can then customize it for your specific deployment needs.

Example `deploy.yml`:

```yaml
name: chat-agent
display_name: Chat Agent
version: 0.1.0

description: |
  Ollama-based chat agent with llama3 model

capabilities:
  runtime: docker
  features:
    - gpu-nvidia
    - docker-optimize

deploy:
  target: linode
  linode:
    image: linode/ubuntu22.04
    region_default: us-mia        # ← Customize
    type_default: g6-standard-8   # ← Customize
    tags:
      - ai
      - chat
    
    container:
      image: ollama/ollama:latest
      internal_port: 11434
      external_port: 80
      
      health:
        type: http
        path: /api/tags
        port: 11434
        success_codes: [200]
        initial_delay_seconds: 120
        timeout_seconds: 10
        max_retries: 30

env:
  required:
    - name: MODEL
      description: Model to use (e.g., llama3)
  optional:
    - name: OLLAMA_MODELS
      description: Directory for model storage
```

### Key Sections

- **name**: Application identifier (used for tagging)
- **capabilities**: Declares what runtime and features are needed
- **deploy.linode.region_default**: Default region (override with `--region`)
- **deploy.linode.type_default**: Default instance type (override with `--linode-type`)
- **deploy.linode.container**: Container configuration (image, ports, health checks)
- **env**: Environment variable requirements

### .env Files

The plugin reads `.env` (or specify with `--env-file`). Format is standard `KEY=VALUE` lines.

- Required variables (defined in `deploy.yml`) are validated
- Optional variables may be left blank
- Values are injected into `/etc/build-ai.env` and passed to Docker

Example `.env`:

```bash
# Required
MODEL=llama3

# Optional
OLLAMA_MODELS=/var/lib/ollama
```

### Variable Expansion

You can use environment variables in container configuration:

```yaml
container:
  command: --model ${MODEL}
  env:
    DATABASE_URL: ${DB_URL}
    LOG_LEVEL: ${LOG_LEVEL:-info}  # Default to "info"
```

### Command-Line Overrides

Override settings from `deploy.yml` at deploy time:

```bash
# Override region
linode-cli build deploy --region us-west

# Override instance type
linode-cli build deploy --linode-type g6-dedicated-16

# Override container image
linode-cli build deploy --container-image myorg/myimage:v2

# Override environment name (for tagging)
linode-cli build deploy --env staging

# Multiple overrides
linode-cli build deploy --region us-east --linode-type g6-standard-4 --env production
```

Command-line arguments always take precedence over `deploy.yml` settings.

---

## BuildWatch Monitoring

BuildWatch provides real-time Docker container monitoring with automatic issue detection.

### Enable BuildWatch

Add to your template's capabilities:

```yaml
capabilities:
  runtime: docker
  features:
    - buildwatch  # Enable monitoring
```

### With Custom Configuration

```yaml
capabilities:
  features:
    - name: buildwatch
      config:
        port: 9090              # API port (default: 9090)
        log_retention_days: 7   # Rotation (default: 7)
        enable_metrics: true    # Metrics (default: true)
```

### Accessing BuildWatch

#### 1. TUI Dashboard

```bash
linode-cli build tui
```

Real-time events, issues, and recommendations.

#### 2. CLI Status

```bash
linode-cli build status --verbose
```

Recent events and detected issues in terminal.

#### 3. HTTP API

```bash
curl http://<instance-ip>:9090/events
curl http://<instance-ip>:9090/issues
curl http://<instance-ip>:9090/status
curl http://<instance-ip>:9090/health
```

#### 4. SSH + Logs

```bash
ssh root@<instance-ip>
tail -f /var/log/build-watcher/events.log
tail -f /var/log/build-watcher/errors.log
systemctl status build-watcher
```

### What BuildWatch Monitors

- ✅ Container starts, stops, restarts
- ✅ Container crashes (with exit codes)
- ✅ OOM (Out of Memory) kills
- ✅ Restart loops (3+ restarts in 5 minutes)
- ✅ System metrics (CPU, memory, disk)

### Issue Detection

**🔴 Critical: OOM Kill (exit code 137)**
- Container killed due to out of memory
- Recommendation: Increase memory or optimize app

**🟡 Warning: Restart Loop**
- 3+ restarts in 5 minutes
- Recommendation: Check application logs

### When to Use BuildWatch

✅ **Recommended for:**
- GPU workloads (detect OOM issues)
- Production deployments
- Long-running services
- Debugging container issues

❌ **Skip for:**
- Simple test deployments
- Minimal resource requirements
- No monitoring needed

---

## Multiple Environments

### Deploy to Different Environments

You can maintain multiple deployment configurations:

```bash
# Production
linode-cli build init llm-api --directory production
cd production
nano deploy.yml
# Set: region_default: us-east, type_default: g6-dedicated-16, tags: [ai, production]
linode-cli build deploy --env production

# Staging
cd ..
linode-cli build init llm-api --directory staging
cd staging
nano deploy.yml
# Set: region_default: us-west, type_default: g6-standard-8, tags: [ai, staging]
linode-cli build deploy --env staging

# Development
cd ..
linode-cli build init llm-api --directory development
cd development
nano deploy.yml
# Set: region_default: us-southeast, type_default: g6-standard-4, tags: [ai, dev]
linode-cli build deploy --env development
```

Each deployment directory has its own `deploy.yml` with different settings!

### Manage Multiple Deployments

```bash
# List all deployments
linode-cli build status

# Destroy specific environment
cd production
linode-cli build destroy  # Infers app from deploy.yml
# or
linode-cli build destroy --app llm-api --env production
```

---

## Deployment Tracking

Deployments are tracked locally at `~/.config/linode-cli.d/ai/ai-deployments.json`.

Each deployment record includes:
- Deployment ID
- Application name and environment
- Linode ID and region
- IP address and hostname
- Template name and version
- Health check configuration
- Timestamps

This allows `status` and `destroy` commands to work without needing `deploy.yml`.

---

## Common Capabilities

Declare requirements in your template without writing setup scripts:

```yaml
capabilities:
  runtime: docker  # or 'native', 'k3s'
  features:
    - gpu-nvidia          # NVIDIA GPU support
    - docker-optimize     # Fast image pulls
    - python-3.11         # Python 3.11
    - nodejs-18           # Node.js 18
    - redis               # Redis server
    - postgresql-14       # PostgreSQL 14
    - buildwatch          # Container monitoring
  packages:
    - ffmpeg
    - libcurl4
    - build-essential
```

See [CAPABILITIES.md](CAPABILITIES.md) for complete reference.

---

## Getting Help

```bash
# Show command help
linode-cli build --help
linode-cli build deploy --help
linode-cli build templates --help

# Show template details
linode-cli build templates show <name>

# List available templates
linode-cli build templates list
```

---

For template development, see [TEMPLATES.md](TEMPLATES.md).

For capabilities reference, see [CAPABILITIES.md](CAPABILITIES.md).
