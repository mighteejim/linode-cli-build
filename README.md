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
| `linode-cli ai templates list` | List built-in AI templates |
| `linode-cli ai templates show <name>` | Show full template metadata |
| `linode-cli ai init <template>` | Scaffold a project directory (`ai.linode.yml`, `.env.example`, README) |
| `linode-cli ai deploy` | Deploy the current project to a single Linode using cloud-init |
| `linode-cli ai status` | Show deployment status/health from the registry and Linode API |
| `linode-cli ai destroy` | Tear down deployments and clean the registry |

## Typical Workflow

```bash
linode-cli ai templates list
linode-cli ai init chat-agent --directory my-agent
cd my-agent
cp .env.example .env   # fill in required values if any
linode-cli ai deploy --region us-chi --linode-type g1-small --wait
linode-cli ai status
linode-cli ai destroy --app chat-agent --env default
```

Deployments are tracked locally at `~/.config/linode-cli.d/ai/ai-deployments.json`, which allows the `status` and `destroy` commands to operate without additional inputs.

## Further Reading

- `docs/template-deployments.md` – End-to-end overview of how manifests, env files, and deployments fit together.
- `linodecli_ai/templates/<template>/docs/README.md` – Template-specific notes (environment variables, ports, usage examples).
