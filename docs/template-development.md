# Template Development Guide

This guide explains how to create custom templates for the Linode CLI AI plugin.

## Overview

Templates are YAML configuration files that define how to deploy AI/ML workloads on Linode. Each template specifies:

- Infrastructure requirements (instance type, region, OS image)
- Container configuration (Docker image, ports, environment)
- Health checks
- Environment variables
- Usage guidance

## Template Structure

A template consists of two required files:

```
template-name/
├── template.yml          # Template specification
└── docs/
    └── README.md         # Usage documentation
```

## Template Specification Format

### Basic Structure

```yaml
name: my-template
display_name: My AI Template
version: 0.1.0

description: >
  Brief description of what this template does and what AI/ML
  workload it's designed for.

deploy:
  target: linode
  linode:
    # OS image to use
    image: linode/ubuntu24.04
    
    # Default region (users can override)
    region_default: us-southeast
    
    # Default instance type (users can override)
    type_default: g6-standard-4
    
    # Tags for organization
    tags:
      - ai
      - your-category
    
    # Container configuration
    container:
      # Docker image to run
      image: your/docker:image
      
      # Port mapping (external -> internal)
      internal_port: 8000
      external_port: 80
      
      # Optional: Override container command
      command: >
        python server.py
      
      # Optional: Environment variables passed to container
      env:
        MODEL_NAME: default-model
      
      # Optional: Script to run after container starts
      post_start_script: |
        #!/bin/bash
        docker exec app initialization-command
      
      # Health check (required)
      health:
        type: http  # or tcp
        path: /health
        port: 8000
        success_codes: [200]
        initial_delay_seconds: 30
        timeout_seconds: 5
        max_retries: 30

# Environment variable requirements
env:
  required:
    - name: API_KEY
      description: API key for authentication
  
  optional:
    - name: MODEL_NAME
      description: Override default model

# Usage guidance (shown after deployment)
guidance:
  summary: |
    Brief explanation of how to use the deployed service.
  
  examples:
    - description: Example API call
      command: curl http://{host}/endpoint
```

### Field Descriptions

#### Top-Level Fields

- **name** (required): Unique template identifier (lowercase with hyphens)
- **display_name** (required): Human-readable name
- **version** (required): Semantic version (e.g., 0.1.0)
- **description** (required): Detailed description of the template

#### Deploy Configuration

- **target**: Always `linode` for now
- **linode.image**: Base OS image (use `linode/ubuntu24.04` for best Docker support)
- **linode.region_default**: Default region code (e.g., `us-southeast`, `us-chi`)
- **linode.type_default**: Default Linode plan (e.g., `g6-standard-4`, `g6-dedicated-8`)
- **linode.tags**: List of tags for organization

#### Container Configuration

- **image** (required): Docker image (e.g., `ollama/ollama:latest`)
- **internal_port** (required): Port the container listens on
- **external_port** (required): Port exposed on the Linode (usually 80 or 443)
- **command** (optional): Override container entrypoint
- **env** (optional): Environment variables passed to container
- **post_start_script** (optional): Bash script executed after container is running

#### Health Check

Health checks ensure the service is running before marking deployment as complete.

**HTTP Health Check:**
```yaml
health:
  type: http
  path: /health
  port: 8000
  success_codes: [200]
  initial_delay_seconds: 30
  timeout_seconds: 5
  max_retries: 30
```

**TCP Health Check:**
```yaml
health:
  type: tcp
  port: 8000
  initial_delay_seconds: 10
  timeout_seconds: 2
  max_retries: 20
```

- **initial_delay_seconds**: Wait time before first health check
- **timeout_seconds**: Timeout for each check
- **max_retries**: Maximum attempts before failing

#### Environment Variables

```yaml
env:
  required:
    - name: VAR_NAME
      description: What this variable is for
  
  optional:
    - name: OPTIONAL_VAR
      description: Optional configuration
```

Required variables must be set by users. Optional variables have defaults or are truly optional.

#### Guidance

```yaml
guidance:
  summary: |
    Explanation of how to use the service after deployment.
    Include API endpoints, authentication, common operations.
  
  examples:
    - description: Health check
      command: curl http://{host}/health
    
    - description: API request
      command: |
        curl -X POST http://{host}/api \
          -H 'Content-Type: application/json' \
          -d '{"input":"test"}'
```

The `{host}` placeholder is replaced with the deployed Linode's IP or hostname.

## Documentation

### docs/README.md

Every template must include comprehensive documentation:

```markdown
# Template Name

## Overview

What this template deploys and what it's used for.

## What Gets Deployed

- Linode instance type: g6-standard-4
- Docker container: your/image:tag
- Exposed port: 80
- Default region: us-southeast

## Prerequisites

- Linode API token
- Any required API keys (e.g., Hugging Face, OpenAI)

## Quick Start

\```bash
# Set required environment variables
export API_KEY=your_key

# Initialize and deploy
linode-cli ai init template-name
linode-cli ai deploy
\```

## Configuration

### Required Environment Variables

- `API_KEY`: Description and where to obtain it

### Optional Environment Variables

- `MODEL_NAME`: Default is `model/name`

## Usage Examples

### Example 1: Basic Usage

\```bash
curl http://YOUR_LINODE_IP/endpoint
\```

### Example 2: With Authentication

\```bash
curl -H "Authorization: Bearer $API_KEY" \
  http://YOUR_LINODE_IP/endpoint
\```

## Performance

- Startup time: ~2 minutes
- Memory usage: ~4GB
- GPU utilization: 80-95% (if applicable)

## Cost Estimates

| Instance Type | Hourly | Monthly | Use Case |
|--------------|--------|---------|----------|
| g6-standard-2 | $0.XX | $XX.XX | Development |
| g6-standard-4 | $0.XX | $XX.XX | Production |

## Troubleshooting

### Issue: Container fails to start

Solution: Check logs with `linode-cli ai status`

### Issue: Out of memory

Solution: Upgrade to larger instance type

## Resources

- [Official Documentation](https://example.com)
- [GitHub Repository](https://github.com/example/repo)
```

## Best Practices

### Container Selection

1. **Use official images** when possible
2. **Pin versions** for reproducibility: `python:3.11-slim`
3. **Optimize size**: Prefer `-slim` or `-alpine` variants

### Health Checks

1. **Always include** a health check
2. **Set appropriate delays** for model loading (LLMs may need 60-120s)
3. **Use realistic timeouts** (account for cold starts)

### Environment Variables

1. **Never hardcode secrets** in template.yml
2. **Document where to obtain API keys**
3. **Provide sensible defaults** for optional variables

### Performance

1. **Choose appropriate instance types** for the workload
2. **Document GPU requirements** clearly
3. **Include memory/storage estimates**

### Security

1. **No hardcoded credentials**
2. **Use HTTPS** when possible (may require additional configuration)
3. **Document security considerations**
4. **Keep Docker images updated**

## Testing Your Template

### 1. Local Testing

Test the Docker container locally:

```bash
docker run -p 80:8000 your/image:tag
curl http://localhost/health
```

### 2. Linode Testing

Deploy and verify:

```bash
# Create test project
mkdir test-template
cd test-template

# Initialize with your template
linode-cli ai init your-template

# Deploy
linode-cli ai deploy --wait

# Verify health
linode-cli ai status

# Test the service
curl http://$(linode-cli ai status --format json | jq -r '.ip')/health

# Clean up
linode-cli ai destroy
```

### 3. Validation

Run validation scripts (from templates repository):

```bash
cd /path/to/linode-cli-ai-templates
python .github/workflows/validate_templates.py
python .github/workflows/validate_index.py
```

## Publishing Your Template

### Option 1: Official Templates Repository

1. Fork [linode-cli-ai-templates](https://github.com/linode/linode-cli-ai-templates)
2. Create your template in `templates/your-template/`
3. Add entry to `index.yml`
4. Submit pull request

See [CONTRIBUTING.md](https://github.com/linode/linode-cli-ai-templates/blob/main/CONTRIBUTING.md) for details.

### Option 2: Private Repository

You can host templates in your own repository:

1. Create repository with same structure
2. Create your own `index.yml`
3. Host on GitHub or any accessible URL
4. Users add your registry:

```bash
# Add custom template source
cat >> ~/.config/linode-cli.d/ai/config.yml << EOF
templates:
  sources:
    - name: my-company
      url: https://raw.githubusercontent.com/my-company/templates/main/index.yml
      enabled: true
EOF

# Update templates
linode-cli ai templates update
```

## Template Categories

Choose appropriate tags for your template:

- **LLM**: `llm`, `text-generation`, `chat`, `completions`
- **Embeddings**: `embeddings`, `vectors`, `semantic-search`
- **Vision**: `vision`, `image-generation`, `object-detection`, `image-classification`
- **Audio**: `audio`, `speech-to-text`, `text-to-speech`, `transcription`
- **Multimodal**: `multimodal`, `vision-language`
- **Fine-tuning**: `fine-tuning`, `training`
- **Agents**: `agents`, `autonomous`, `tools`
- **Infrastructure**: `api`, `inference`, `serving`

## Examples

### Example 1: Simple LLM API

```yaml
name: simple-llm
display_name: Simple LLM API
version: 0.1.0

description: >
  Basic text generation API using a small language model.

deploy:
  target: linode
  linode:
    image: linode/ubuntu24.04
    region_default: us-southeast
    type_default: g6-standard-4
    tags:
      - ai
      - llm
      - api
    container:
      image: vllm/vllm-openai:latest
      internal_port: 8000
      external_port: 80
      env:
        MODEL_NAME: TinyLlama/TinyLlama-1.1B-Chat-v1.0
      health:
        type: http
        path: /health
        port: 8000
        success_codes: [200]
        initial_delay_seconds: 60
        timeout_seconds: 5
        max_retries: 20

env:
  required: []
  optional:
    - name: HF_TOKEN
      description: Hugging Face token for gated models

guidance:
  summary: |
    OpenAI-compatible text generation API.
  examples:
    - description: List models
      command: curl http://{host}/v1/models
    - description: Generate text
      command: |
        curl -X POST http://{host}/v1/completions \
          -H 'Content-Type: application/json' \
          -d '{"model":"TinyLlama/TinyLlama-1.1B-Chat-v1.0","prompt":"Hello"}'
```

### Example 2: GPU-Accelerated Service

```yaml
name: stable-diffusion
display_name: Stable Diffusion XL
version: 0.1.0

description: >
  Stable Diffusion XL image generation API with GPU acceleration.

deploy:
  target: linode
  linode:
    image: linode/ubuntu24.04
    region_default: us-southeast
    type_default: g6-dedicated-8  # GPU instance
    tags:
      - ai
      - vision
      - image-generation
      - gpu
    container:
      image: stabilityai/stable-diffusion:latest
      internal_port: 8000
      external_port: 80
      command: >
        python -m serve --model sdxl-1.0
      health:
        type: http
        path: /health
        port: 8000
        success_codes: [200]
        initial_delay_seconds: 120  # Model loading takes time
        timeout_seconds: 10
        max_retries: 30

env:
  required:
    - name: HF_TOKEN
      description: Hugging Face token to download SDXL model
  optional: []

guidance:
  summary: |
    Text-to-image generation API. POST to /generate with a prompt.
  examples:
    - description: Generate image
      command: |
        curl -X POST http://{host}/generate \
          -H 'Content-Type: application/json' \
          -d '{"prompt":"A serene mountain landscape"}' \
          --output image.png
```

## Getting Help

- **Issues**: [GitHub Issues](https://github.com/linode/linode-cli-ai/issues)
- **Discussions**: [GitHub Discussions](https://github.com/linode/linode-cli-ai-templates/discussions)
- **Documentation**: [Linode Docs](https://www.linode.com/docs/)

## Resources

- [Template Repository](https://github.com/linode/linode-cli-ai-templates)
- [Contributing Guidelines](https://github.com/linode/linode-cli-ai-templates/blob/main/CONTRIBUTING.md)
- [Existing Templates](https://github.com/linode/linode-cli-ai-templates/tree/main/templates)
- [Docker Documentation](https://docs.docker.com/)
- [Cloud-init Documentation](https://cloudinit.readthedocs.io/)
