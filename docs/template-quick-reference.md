# Template System Quick Reference

## New Commands

### Scaffold a Template

Create a new template with LLM assistance:

```bash
linode-cli ai templates scaffold <name> --llm-assist
```

Create a new template interactively:

```bash
linode-cli ai templates scaffold <name>
```

### Validate a Template

Check template for errors:

```bash
linode-cli ai templates validate <path>
```

Examples:
```bash
linode-cli ai templates validate my-template/
linode-cli ai templates validate my-template/template.yml
linode-cli ai templates validate ./template.yml
```

### Test a Template

Preview cloud-init (dry run):

```bash
linode-cli ai templates test <name-or-path> --dry-run
```

Examples:
```bash
# Test bundled template
linode-cli ai templates test llm-api --dry-run

# Test local template
linode-cli ai templates test ./my-template --dry-run
linode-cli ai templates test my-template/template.yml --dry-run
```

## Template Capabilities

### Declare Runtime

```yaml
capabilities:
  runtime: docker  # or native, k3s
```

### Add Features

```yaml
capabilities:
  features:
    - gpu-nvidia          # NVIDIA GPU support
    - docker-optimize     # 10 concurrent downloads
    - python-3.11         # Python 3.11
    - nodejs-18           # Node.js 18
    - redis               # Redis server
    - postgresql-14       # PostgreSQL 14
```

### Add Custom Packages

```yaml
capabilities:
  packages:
    - ffmpeg
    - libcurl4
    - build-essential
```

## Complete Example

```yaml
name: my-api
display_name: My API
version: 0.1.0

description: |
  Description of what this template does.

capabilities:
  runtime: docker
  features:
    - gpu-nvidia
    - redis
  packages:
    - ffmpeg

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
      image: myorg/myapp:latest
      internal_port: 8000
      external_port: 80
      command: --model ${MODEL}
      env:
        MODEL: default-model
      
      health:
        type: http
        path: /health
        port: 8000
        success_codes: [200]
        initial_delay_seconds: 120
        timeout_seconds: 10
        max_retries: 30

env:
  required:
    - name: API_KEY
      description: Your API key
  
  optional:
    - name: MODEL
      description: |
        Model to use. Options:
        - small-model (fast)
        - large-model (accurate)
        Default: default-model

guidance:
  summary: |
    API exposed on port 80.
    Model loading takes ~2 minutes.
  
  examples:
    - description: Health check
      command: curl http://{host}/health
    
    - description: API call
      command: |
        curl -X POST http://{host}/api \
          -H 'Content-Type: application/json' \
          -d '{"input": "data"}'
```

## Workflow

### 1. LLM-Assisted Creation

```bash
# Create scaffold
linode-cli ai templates scaffold my-api --llm-assist

# Answer questions
# - Service description
# - GPU requirement
# - Dependencies
# - Container image
# - Health check details

# Feed to LLM in Cursor/Claude
# "@my-api/llm-instructions.md complete this template"

# Validate
linode-cli ai templates validate my-api/

# Test
linode-cli ai templates test my-api --dry-run

# Deploy
linode-cli ai init my-api
cd my-api
# Edit .env
linode-cli ai deploy --wait
```

### 2. Manual Creation

```bash
# Create directory
mkdir -p my-api/docs

# Create template.yml
# (use example above)

# Validate
linode-cli ai templates validate my-api/

# Test
linode-cli ai templates test my-api --dry-run

# Deploy
linode-cli ai init my-api
cd my-api
linode-cli ai deploy --wait
```

## Common Patterns

### GPU Template

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

### CPU Template

```yaml
capabilities:
  runtime: docker

deploy:
  linode:
    image: linode/ubuntu24.04
    type_default: g6-standard-2
```

### With Redis

```yaml
capabilities:
  runtime: docker
  features:
    - redis

deploy:
  linode:
    container:
      env:
        REDIS_URL: redis://localhost:6379
```

### With Python

```yaml
capabilities:
  runtime: native
  features:
    - python-3.11
  packages:
    - python3-pip
```

## Validation Checklist

Before deploying, ensure:

- [ ] All required fields present
- [ ] Capabilities instead of `requires_gpu`
- [ ] Health check configured
- [ ] Environment variables documented
- [ ] Guidance section with examples
- [ ] Correct base image (ubuntu22.04 for GPU)
- [ ] Appropriate instance type
- [ ] Semantic version (X.Y.Z)

## Troubleshooting

**Validation fails with missing fields:**
→ Check required fields: name, display_name, version, description, deploy

**Warning about requires_gpu:**
→ Replace with `capabilities.features: [gpu-nvidia]`

**Health check fails:**
→ Increase `initial_delay_seconds`
→ Verify `path` and `port` are correct

**GPU issues:**
→ Use `linode/ubuntu22.04` base image
→ Use `g6-*` instance type

## Resources

- [Template Development Guide](template-development.md)
- [Implementation Summary](../IMPLEMENTATION_SUMMARY.md)
- [Example Templates](../linodecli_ai/templates/)

## Getting Help

```bash
# Show template details
linode-cli ai templates show <name>

# List available templates
linode-cli ai templates list

# Show command help
linode-cli ai templates --help
linode-cli ai templates scaffold --help
linode-cli ai templates validate --help
linode-cli ai templates test --help
```
