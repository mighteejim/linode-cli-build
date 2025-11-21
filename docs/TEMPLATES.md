# Template Development Guide

Complete guide to creating, testing, and publishing templates for `linode-cli build`.

## Table of Contents

1. [Overview](#overview)
2. [Quick Start](#quick-start)
3. [Template Structure](#template-structure)
4. [Capabilities System](#capabilities-system)
5. [Best Practices](#best-practices)
6. [LLM-Assisted Development](#llm-assisted-development)
7. [Validation and Testing](#validation-and-testing)
8. [Publishing Templates](#publishing-templates)

---

## Overview

Templates define how to deploy AI services to Linode cloud instances. They specify:

- **What to deploy**: Container images, ports, environment variables
- **Where to deploy**: Default region, instance type, base OS image
- **How to set up**: System requirements using capabilities or custom scripts
- **How to use**: Documentation, examples, and guidance

Templates use a **declarative approach** with the capabilities system, making them easy to create and maintain without writing shell scripts.

---

## Quick Start

### Option 1: LLM-Assisted (Recommended)

Use AI assistance to generate templates quickly:

```bash
linode-cli build templates scaffold my-api --llm-assist

# Answer a few questions:
# - What service? (e.g., "FastAPI ML inference API")
# - Requires GPU? (y/n)
# - Dependencies? (e.g., "PyTorch, Redis")
# - Container image? (e.g., "pytorch/pytorch:latest")
# - Health check? (e.g., "/health")
# - Startup time? (e.g., "120" seconds)

# This creates:
# - my-api/template-stub.yml (basic structure)
# - my-api/llm-instructions.md (comprehensive guide for LLM)
# - my-api/docs/README-stub.md
# - my-api/.env.example

# Feed to your LLM (Cursor, Claude, GPT-4):
# "@my-api/llm-instructions.md complete this template"
```

### Option 2: Interactive

Answer detailed questions to generate a complete template:

```bash
linode-cli build templates scaffold my-api

# Answer detailed questions about:
# - Display name, description
# - Runtime (Docker, native)
# - GPU requirements
# - Container details
# - Health checks
# - Environment variables
```

### Option 3: Manual Creation

Create from scratch following the [Template Structure](#template-structure).

---

## Template Structure

A template consists of:

```
my-template/
├── template.yml          # Main template definition
├── docs/
│   └── README.md        # Documentation
└── .env.example         # Example environment variables (optional)
```

### Minimal template.yml

```yaml
name: my-template
display_name: My Template
version: 0.1.0

description: |
  What this template does and what it's used for.

capabilities:
  runtime: docker
  features:
    - gpu-nvidia  # If GPU needed

deploy:
  target: linode
  linode:
    image: linode/ubuntu22.04
    region_default: us-mia
    type_default: g6-standard-8
    tags:
      - ai
    
    container:
      image: myorg/myapp:latest
      internal_port: 8000
      external_port: 80
      
      health:
        type: http
        path: /health
        port: 8000
        success_codes: [200]
        initial_delay_seconds: 60
        timeout_seconds: 10
        max_retries: 30

env:
  required: []
  optional: []

guidance:
  summary: |
    How to use this service after deployment.
  examples:
    - description: Check health
      command: curl http://{host}/health
```

---

## Capabilities System

The capabilities system lets you declare requirements without writing setup scripts.

### Runtime

Specify the runtime environment:

```yaml
capabilities:
  runtime: docker  # or 'native', 'k3s'
```

- **docker**: Installs Docker and runs containerized services (most common)
- **native**: No container, for native binaries or scripts
- **k3s**: Lightweight Kubernetes (advanced)

### Features

Declare common features your service needs:

```yaml
capabilities:
  features:
    - gpu-nvidia          # NVIDIA GPU drivers + container toolkit
    - docker-optimize     # Enable 10 concurrent downloads
    - python-3.11         # Python 3.11 runtime
    - nodejs-18           # Node.js 18 runtime
    - redis               # Redis server
    - postgresql-14       # PostgreSQL 14 server
    - buildwatch          # Container monitoring
```

Available features:

| Feature | Description |
|---------|-------------|
| `gpu-nvidia` | NVIDIA drivers (535) + Container Toolkit |
| `docker-optimize` | Parallel Docker layer downloads (10 concurrent) |
| `python-3.10` | Python 3.10 runtime |
| `python-3.11` | Python 3.11 runtime |
| `python-3.12` | Python 3.12 runtime |
| `nodejs-18` | Node.js 18 runtime |
| `nodejs-20` | Node.js 20 runtime |
| `redis` | Redis server (auto-started) |
| `postgresql-14` | PostgreSQL 14 server |
| `postgresql-15` | PostgreSQL 15 server |
| `buildwatch` | Container monitoring and issue detection |

### BuildWatch Monitoring

BuildWatch provides real-time Docker container monitoring and issue detection.

#### Basic Usage

```yaml
capabilities:
  features:
    - buildwatch
```

#### Configuration Options

```yaml
capabilities:
  features:
    - name: buildwatch
      config:
        port: 9090              # HTTP API port (default: 9090)
        log_retention_days: 7   # Log rotation (default: 7)
        enable_metrics: true    # Resource metrics (default: true)
```

#### Features

- Real-time Docker event streaming
- Automatic issue detection (OOM kills, crash loops)
- HTTP API on port 9090
- Container lifecycle tracking
- Resource metrics collection

#### API Endpoints

- `http://<instance-ip>:9090/health` - Service health
- `http://<instance-ip>:9090/status` - Current status
- `http://<instance-ip>:9090/events` - Recent events
- `http://<instance-ip>:9090/issues` - Detected issues

#### When to Use BuildWatch

✅ **Recommended:**
- GPU workloads (detect OOM issues)
- Production deployments (issue alerting)
- Long-running services (uptime tracking)
- Development (debugging container issues)

❌ **Skip for:**
- Simple test deployments
- Minimal resource usage requirements
- No container monitoring needed

### Custom Packages

Install additional system packages:

```yaml
capabilities:
  packages:
    - libcurl4
    - build-essential
    - ffmpeg
```

### Complete Example

```yaml
capabilities:
  runtime: docker
  features:
    - gpu-nvidia
    - docker-optimize
    - redis
    - buildwatch
  packages:
    - libopencv-dev
```

This installs:
- Docker runtime
- NVIDIA GPU support
- Redis server
- BuildWatch monitoring
- Custom packages

---

## Best Practices

### 1. GPU Templates

**Do:**
- Use `capabilities.features: [gpu-nvidia]` instead of `requires_gpu: true`
- Use `linode/ubuntu22.04` base image (proven stable for GPU)
- Set generous health check timeouts (3+ minutes for model loading)
- Enable Docker optimization: `features: [gpu-nvidia, docker-optimize]`

**Example:**

```yaml
capabilities:
  runtime: docker
  features:
    - gpu-nvidia
    - docker-optimize

deploy:
  linode:
    image: linode/ubuntu22.04
    type_default: g6-standard-8
    container:
      health:
        initial_delay_seconds: 180
        max_retries: 60
```

### 2. Environment Variables

**Clear descriptions with examples:**

```yaml
env:
  required:
    - name: API_KEY
      description: Your service API key (get from dashboard)
  
  optional:
    - name: MODEL_NAME
      description: |
        HuggingFace model to load. Popular options:
        - microsoft/Phi-3-mini-4k-instruct (4k context)
        - mistralai/Mistral-7B-Instruct-v0.3 (32k context)
        - meta-llama/Meta-Llama-3-8B-Instruct (8k context, gated)
        Default: meta-llama/Meta-Llama-3-8B-Instruct
```

**Variable expansion in container config:**

```yaml
container:
  command: --model ${MODEL_NAME:-default-model}
  env:
    DATABASE_URL: ${DB_URL}
```

### 3. Health Checks

**Always include health checks:**

```yaml
health:
  type: http
  path: /health
  port: 8000
  success_codes: [200]
  initial_delay_seconds: 60  # Adjust for your service
  timeout_seconds: 10
  max_retries: 30  # 5 minutes total
```

**Timing guidelines:**
- Simple services: `initial_delay_seconds: 10-30`
- Model loading: `initial_delay_seconds: 60-180`
- Large models: `initial_delay_seconds: 180-300`

### 4. Volume Mounts

**Mount host directories into containers:**

```yaml
container:
  image: pytorch/pytorch:2.0.0-cuda11.7-cudnn8-runtime
  command: python /app/main.py
  volumes:
    - /app:/app          # Mount application code
    - /data:/data        # Mount data directory
    - /models:/models    # Mount model files
```

### 5. Documentation

**Include helpful guidance:**

```yaml
guidance:
  summary: |
    This template deploys a FastAPI ML inference service.
    
    The API is exposed on port 80. Use {host} in examples below
    to refer to your Linode's hostname.
    
    Model loading takes 2-3 minutes on first start.
  
  examples:
    - description: Check service health
      command: curl http://{host}/health
    
    - description: Run inference
      command: |
        curl -X POST http://{host}/predict \
          -H 'Content-Type: application/json' \
          -d '{"input": "your data here"}'
```

### 6. Instance Sizing

**Choose appropriate defaults:**

| Workload | Instance Type | GPU | RAM | Use Case |
|----------|---------------|-----|-----|----------|
| Small models (< 7B) | `g6-standard-4` | 1x RTX 6000 Ada | 16GB | Development, small models |
| Medium models (7-13B) | `g6-standard-8` | 1x RTX 6000 Ada | 32GB | Production, medium models |
| Large models (13-30B) | `g6-dedicated-16` | 1x RTX 6000 Ada | 64GB | Large models |
| CPU workloads | `g6-standard-2` | None | 8GB | Utilities, embeddings |

### 7. Base Images

**GPU workloads:**
- Use: `linode/ubuntu22.04` (proven stability)
- Avoid: Debian, Alpine (driver issues)

**CPU workloads:**
- Use: `linode/ubuntu24.04` (latest LTS)
- Alternative: `linode/debian12`

### 8. Version Management

**Semantic versioning:**
```yaml
version: 0.1.0  # MAJOR.MINOR.PATCH
```

- **MAJOR**: Breaking changes
- **MINOR**: New features (backward compatible)
- **PATCH**: Bug fixes

### 9. Tags

**Use descriptive tags:**

```yaml
tags:
  - ai
  - llm  # or embeddings, vision, etc.
  - gpu  # if GPU required
  - production  # or development, experimental
```

---

## LLM-Assisted Development

The LLM-assisted workflow leverages AI to help you create production-ready templates quickly.

### How It Works

1. **Run scaffold with `--llm-assist`:**
   ```bash
   linode-cli build templates scaffold pytorch-serve --llm-assist
   ```

2. **Answer high-level questions:**
   - Service description
   - GPU requirements
   - Dependencies
   - Container image
   - Health check details

3. **Get comprehensive context:**
   - `template-stub.yml`: Basic structure with your inputs
   - `llm-instructions.md`: Complete guide for LLM with:
     - Template system documentation
     - Capability reference
     - Example templates
     - Schema reference
     - Best practices
     - Validation checklist

4. **Feed to your LLM:**
   ```
   In Cursor/Claude/GPT-4:
   "@llm-instructions.md complete this template for PyTorch model serving"
   ```

5. **LLM generates:**
   - Complete `template.yml`
   - Appropriate capabilities
   - Health checks with correct timing
   - Environment variable documentation
   - Usage examples

6. **Validate and test:**
   ```bash
   linode-cli build templates validate pytorch-serve
   linode-cli build templates test pytorch-serve --dry-run
   ```

### Benefits

- **Fast**: Create complex templates in minutes
- **Best practices**: LLM applies proven patterns automatically
- **Comprehensive**: All sections filled out with helpful docs
- **Learning tool**: Study generated templates to understand the system

---

## Validation and Testing

### Validate Template

Check template correctness before deploying:

```bash
linode-cli build templates validate my-template/

# Or validate specific file
linode-cli build templates validate my-template/template.yml
```

**Checks:**
- Required fields present
- Correct data types
- Valid capabilities
- Health check configuration
- GPU configuration (image, instance type)
- Semantic versioning

### Test Template Deployment

Test your template with a real deployment:

```bash
# Manual test deployment
linode-cli build init my-template --directory my-deployment
cd my-deployment
# Review and customize deploy.yml if needed
nano deploy.yml
cp .env.example .env
# Configure .env
linode-cli build deploy --wait
linode-cli build status

# Clean up
linode-cli build destroy
```

---

## Publishing Templates

### Installing Templates for Local Use

Once you've developed and tested a template, you can install it for reuse:

```bash
# Install your template
linode-cli build templates install ./my-template

# Now use it like a bundled template
linode-cli build init my-template --directory deployment
```

Your installed templates are stored at `~/.config/linode-cli.d/build/templates/` and won't be overwritten during plugin upgrades.

### Uninstalling Templates

```bash
# Remove an installed template
linode-cli build templates uninstall my-template
```

### Contributing Templates to the Plugin

To add your template to the bundled templates (available to all users):

1. Fork the repository
2. Add your template to `linodecli_build/templates/your-template/`
3. Add entry to `linodecli_build/templates/index.yml`:
   ```yaml
   templates:
     - name: your-template
       path: templates/your-template/template.yml
   ```
4. Submit a pull request

Your template will ship with the next plugin release!

---

## Complete Schema Reference

```yaml
# Required fields
name: string                    # Unique identifier (lowercase, hyphens)
display_name: string            # Human-readable name
version: string                 # Semantic version (X.Y.Z)
description: string             # Multi-line description

# Optional capabilities
capabilities:
  runtime: docker | native | k3s
  features:
    - gpu-nvidia
    - docker-optimize
    - buildwatch
    # ... other features
  packages:
    - libcurl4
    # ... other packages

# Required deployment config
deploy:
  target: linode
  linode:
    image: string               # Base OS image
    region_default: string      # Default region
    type_default: string        # Default instance type
    tags: [string]              # Organization tags
    
    container:                  # For Docker runtime
      image: string             # Docker image
      internal_port: integer    # Container port
      external_port: integer    # Host port
      command: string           # Optional CMD override
      env: object               # Default env vars
      volumes: [string]         # Volume mounts
      
      health:                   # Health check (recommended)
        type: http | tcp | exec
        path: string            # For HTTP
        port: integer
        success_codes: [integer]
        initial_delay_seconds: integer
        timeout_seconds: integer
        max_retries: integer

# Optional environment variables
env:
  required:
    - name: string
      description: string
  optional:
    - name: string
      description: string

# Optional usage guidance
guidance:
  summary: string               # Usage instructions
  examples:
    - description: string
      command: string
```

---

## Troubleshooting

### Template Won't Validate

**Error: Missing required fields**
- Ensure all required fields are present: name, display_name, version, description, deploy

**Error: Invalid capability**
- Check capability name spelling
- See [Capabilities System](#capabilities-system) for valid features

**Warning: Using deprecated requires_gpu**
- Replace `requires_gpu: true` with `capabilities.features: [gpu-nvidia]`

### Health Check Timing

**Health check fails immediately**
- Increase `initial_delay_seconds`
- Check `path` is correct
- Verify `port` matches internal_port

**Health check times out**
- Increase `max_retries`
- Check service actually starts
- Look at Linode console logs

### GPU Issues

**Error: GPU instance but wrong image**
- Use `linode/ubuntu22.04` for GPU instances

**Warning: GPU capability without GPU instance**
- Instance type should start with `g6-`

---

## Additional Resources

- [User Guide](GUIDE.md) - Deployment and usage
- [Capabilities Reference](CAPABILITIES.md) - Complete capability documentation
- [Example Templates](../linodecli_build/templates/) - Bundled templates

---

## Getting Help

```bash
# Show command help
linode-cli build templates --help
linode-cli build templates scaffold --help
linode-cli build templates validate --help

# Show template details
linode-cli build templates show <name>

# List available templates
linode-cli build templates list
```
