# linode-cli ai Plugin

Prototype plugin that extends `linode-cli` with an `ai` command namespace for deploying AI demo apps to Linode instances. Phase 1 focuses on single-Linode deployments driven by cloud-init and public container images.

## Installation

```bash
pip install linodecli-ai
linode-cli register-plugin linodecli_ai
```

This plugin relies on the existing `linode-cli` authentication and configuration.

### Build From Source

If you are working inside this repository and want to use the latest code:

```bash
# 1. Clone the repo (if you haven't already)
git clone https://github.com/linode/linode-cli-ai.git
cd linode-cli-ai

# 2. Install dependencies in editable mode
pip install -e .

# 3. Register the plugin with linode-cli
linode-cli register-plugin linodecli_ai
```

You can unregister with `linode-cli unregister-plugin ai` if you need to clean up.

## Commands Overview

| Command | Description |
| --- | --- |
| `linode-cli ai templates list` | List available AI templates (bundled and remote) |
| `linode-cli ai templates show <name>` | Show full template metadata |
| `linode-cli ai templates update` | Update templates from remote registry |
| `linode-cli ai templates install <name>` | Download a specific template |
| `linode-cli ai templates remove <name>` | Remove a cached template |
| `linode-cli ai init <template>` | Scaffold a project directory (`ai.linode.yml`, `.env.example`, README) |
| `linode-cli ai deploy` | Deploy the current project to a single Linode using cloud-init |
| `linode-cli ai status` | Show deployment status/health from the registry and Linode API |
| `linode-cli ai destroy` | Tear down deployments and clean the registry |

## Available Templates

The plugin includes 3 bundled templates and supports remote templates from the [linode-cli-ai-templates](https://github.com/linode/linode-cli-ai-templates) repository.

### Bundled Templates

- **chat-agent**: Ollama-based chat agent (llama3)
- **llm-api**: vLLM-based text generation API (OpenAI-compatible)
- **embeddings-python**: Sentence-transformers embeddings server (all-mpnet-base-v2)

### Remote Templates

Additional templates are available from the community template registry. The plugin automatically checks for and downloads templates from the remote registry as needed.

```bash
# List all available templates (bundled + remote)
linode-cli ai templates list

# Update templates from registry
linode-cli ai templates update

# Install a specific template version
linode-cli ai init chat-agent@0.2.0
```

### Template Versioning

Templates support semantic versioning. You can specify a version when initializing:

```bash
# Use latest version (default)
linode-cli ai init chat-agent

# Use specific version
linode-cli ai init chat-agent@0.1.0
```

## Typical Workflow

```bash
# List available templates
linode-cli ai templates list

# Initialize a project from a template
linode-cli ai init chat-agent --directory my-agent
cd my-agent

# Configure environment (if needed)
cp .env.example .env   # fill in required values if any

# Deploy to Linode
linode-cli ai deploy --region us-chi --linode-type g6-standard-2 --wait

# Check deployment status
linode-cli ai status

# Destroy when done
linode-cli ai destroy --app chat-agent --env default
```

Deployments are tracked locally at `~/.config/linode-cli.d/ai/ai-deployments.json`, which allows the `status` and `destroy` commands to operate without additional inputs.

## Further Reading

- `docs/template-deployments.md` – End-to-end overview of how manifests, env files, and deployments fit together.
- `docs/template-development.md` – Guide for creating custom templates.
- `linodecli_ai/templates/<template>/docs/README.md` – Template-specific notes (environment variables, ports, usage examples).
- [Template Repository](https://github.com/linode/linode-cli-ai-templates) – Community templates and contribution guidelines.

## Configuration

The plugin stores configuration at `~/.config/linode-cli.d/ai/config.yml`. You can customize:

- Template registry URL
- Template cache directory
- Auto-update behavior
- Update check interval

Example configuration:

```yaml
templates:
  registry_url: https://raw.githubusercontent.com/linode/linode-cli-ai-templates/main/index.yml
  cache_dir: ~/.config/linode-cli.d/ai/templates
  auto_update: true
  update_check_interval: 86400  # 24 hours
  sources:
    - name: official
      url: https://raw.githubusercontent.com/linode/linode-cli-ai-templates/main/index.yml
      enabled: true
```

## Contributing Templates

We welcome community contributions! To create and share your own templates:

1. Fork the [linode-cli-ai-templates](https://github.com/linode/linode-cli-ai-templates) repository
2. Create your template following the [Template Development Guide](docs/template-development.md)
3. Submit a pull request with your template

See [CONTRIBUTING.md](https://github.com/linode/linode-cli-ai-templates/blob/main/CONTRIBUTING.md) in the templates repository for detailed guidelines.
