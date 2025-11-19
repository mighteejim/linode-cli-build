# Template Deployment Workflow

This plugin assumes a simple, repeatable deployment layout. Every deployment created
via `linode-cli ai init <template>` contains:

1. **`deploy.yml`** – Complete deployment configuration (what to deploy + where to deploy).
   This file combines the template definition with deployment-specific settings.
2. **`.env`** – User-provided environment variables that will be injected into
   the container.
3. **`README.md`** – Quickstart notes specific to the chosen template.

## Lifecycle

1. Initialize deployment:
   ```bash
   linode-cli ai init chat-agent --directory chat-demo
   cd chat-demo
   ```

2. Review and customize deployment configuration:
   ```bash
   cat deploy.yml          # Review settings
   nano deploy.yml         # Optional: customize region, instance type, etc.
   cp .env.example .env    # Configure environment variables
   nano .env               # Fill in required values
   ```

3. Deploy:
   ```bash
   linode-cli ai deploy --wait
   ```

4. Check status:
   ```bash
   linode-cli ai status
   ```

5. Destroy when finished:
   ```bash
   linode-cli ai destroy
   ```

## `deploy.yml`

This file contains everything needed for deployment. When you run `linode-cli ai init`,
the template is copied to `deploy.yml` in your deployment directory. You can then
customize it for your specific deployment needs.

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
    region_default: us-mia        # ← Customize for your deployment
    type_default: g6-standard-8   # ← Customize for your deployment
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

guidance:
  summary: |
    Chat agent is available at http://{host}
  examples:
    - description: Test the API
      command: curl http://{host}/api/tags
```

### Key Sections

- **`name`**: Application identifier (used for tagging)
- **`capabilities`**: Declares what runtime and features are needed (GPU, Docker, etc.)
- **`deploy.linode.region_default`**: Default region (can override with `--region`)
- **`deploy.linode.type_default`**: Default instance type (can override with `--linode-type`)
- **`deploy.linode.container`**: Container configuration (image, ports, health checks)
- **`env`**: Environment variable requirements

### Customizing for Different Environments

You can maintain multiple deployment configurations:

```bash
# Production
linode-cli ai init llm-api --directory production
cd production
nano deploy.yml
# Set: region_default: us-east, type_default: g6-dedicated-16, tags: [ai, production]

# Staging
linode-cli ai init llm-api --directory staging
cd staging
nano deploy.yml
# Set: region_default: us-west, type_default: g6-standard-8, tags: [ai, staging]

# Development
linode-cli ai init llm-api --directory development
cd development
nano deploy.yml
# Set: region_default: us-southeast, type_default: g6-standard-4, tags: [ai, dev]
```

Each deployment directory has its own `deploy.yml` with different settings!

## `.env` Files

The plugin reads `.env` (or specify a different file with `--env-file`). Format is
standard `KEY=VALUE` lines. Comments begin with `#`.

- Required variables (defined in `deploy.yml`) are validated; deployment fails if any are missing.
- Optional variables may be left blank (or omitted) if the template supports sensible defaults.
- Values are injected into `/etc/build-ai.env` on the Linode and passed to Docker via `--env-file`.

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

Variables from `.env` are expanded in:
- `container.command`
- `container.env` values

## Command-Line Overrides

You can override settings from `deploy.yml` at deploy time:

```bash
# Override region
linode-cli ai deploy --region us-west

# Override instance type
linode-cli ai deploy --linode-type g6-dedicated-16

# Override container image
linode-cli ai deploy --container-image myorg/myimage:v2

# Override environment name (for tagging)
linode-cli ai deploy --env staging

# Multiple overrides
linode-cli ai deploy --region us-east --linode-type g6-standard-4 --env production
```

Command-line arguments always take precedence over `deploy.yml` settings.

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

## Multiple Deployments

You can have multiple deployments from the same template:

```bash
# Production deployment
linode-cli ai init llm-api --directory prod
cd prod
nano deploy.yml  # region: us-east, type: g6-dedicated-16
linode-cli ai deploy --env production

# Staging deployment
cd ..
linode-cli ai init llm-api --directory staging
cd staging
nano deploy.yml  # region: us-west, type: g6-standard-8
linode-cli ai deploy --env staging

# List all deployments
linode-cli ai status

# Destroy specific environment
cd prod
linode-cli ai destroy  # Infers app from deploy.yml
# or
linode-cli ai destroy --app llm-api --env production
```

## Template Development

When developing templates, the file is named `template.yml` in the template source
directory. When initialized for deployment, it's copied to `deploy.yml`:

```bash
# Template source (during development)
templates/
  my-template/
    template.yml       # Template definition
    docs/
      README.md
    .env.example

# After initialization (for deployment)
deployment/
  deploy.yml          # Copied from template.yml
  .env                # Created from .env.example
  README.md           # Copied from template
```

This separation keeps template authoring and deployment concerns separate:
- **`template.yml`**: Template definition (during development)
- **`deploy.yml`**: Deployment configuration (for users)

See [Template Development Guide](template-development.md) for more details.
