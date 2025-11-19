# 🚀 linode-cli ai Plugin

**Deploy AI services to Linode in minutes with simple, declarative templates.**

A `linode-cli` plugin that makes deploying AI applications as easy as running a single command. Perfect for LLM APIs, chat agents, embeddings servers, and more.

---

## ✨ Features

- 🎯 **Simple Workflow** - Init, customize, deploy. That's it.
- 🤖 **AI-Ready Templates** - Pre-configured for GPU workloads, LLMs, embeddings, and more
- 📦 **Template System** - Use bundled templates or create your own
- 🔧 **Fully Customizable** - Override any setting per deployment
- 🌐 **Multi-Environment** - Deploy prod, staging, dev from the same template
- 🏥 **Health Checks** - Automatic health monitoring for your services
- 📊 **Status Tracking** - See all deployments and their health at a glance

---

## 📦 Installation

```bash
pip install linodecli-ai
linode-cli register-plugin linodecli_ai
```

This plugin uses your existing `linode-cli` authentication and configuration.

### 🛠️ Build From Source

```bash
# Clone the repository
git clone https://github.com/linode/linode-cli-ai.git
cd linode-cli-ai

# Install in editable mode
pip install -e .

# Register the plugin
linode-cli register-plugin linodecli_ai
```

---

## 🚀 Quick Start

Deploy an LLM API in under 2 minutes:

```bash
# 1. Initialize from template
linode-cli ai init llm-api --directory my-llm
cd my-llm

# 2. Configure (optional)
nano deploy.yml  # Customize region, instance type, etc.
cp .env.example .env  # Set your environment variables

# 3. Deploy!
linode-cli ai deploy --wait

# 4. Check status
linode-cli ai status
```

That's it! Your LLM API is now running on Linode with GPU support.

---

## 📚 Commands Reference

### Template Management

| Command | Description |
|---------|-------------|
| `linode-cli ai templates list` | 📋 List available templates |
| `linode-cli ai templates show <name>` | 🔍 Show template details |
| `linode-cli ai templates scaffold <name>` | ✏️ Create a new template |
| `linode-cli ai templates validate <path>` | ✅ Validate template syntax |
| `linode-cli ai templates test <name> --dry-run` | 🧪 Preview deployment config |
| `linode-cli ai templates update` | 🔄 Update from remote registry |

### Deployment Lifecycle

| Command | Description |
|---------|-------------|
| `linode-cli ai init <template>` | 🎬 Initialize a new deployment |
| `linode-cli ai deploy` | 🚀 Deploy to Linode |
| `linode-cli ai status` | 📊 Check deployment status |
| `linode-cli ai destroy` | 💣 Tear down deployment |

---

## 🎨 Available Templates

### Bundled Templates

| Template | Description | GPU |
|----------|-------------|-----|
| **chat-agent** | Ollama-based chat agent with Llama 3 | ✅ |
| **llm-api** | vLLM text generation API (OpenAI-compatible) | ✅ |
| **embeddings-python** | Sentence-transformers embeddings server | ❌ |

### 🌐 Community Templates

Explore more templates in the [community registry](https://github.com/linode/linode-cli-ai-templates):

```bash
# List all available templates
linode-cli ai templates list

# Update templates from registry
linode-cli ai templates update

# Use a specific version
linode-cli ai init chat-agent@0.2.0
```

---

## 💡 Example Workflows

### Deploy Multiple Environments

Use the same template for different environments:

```bash
# Production
linode-cli ai init llm-api --directory prod
cd prod
nano deploy.yml  # region: us-east, type: g6-dedicated-16
linode-cli ai deploy --wait

# Staging
linode-cli ai init llm-api --directory staging
cd staging
nano deploy.yml  # region: us-west, type: g6-standard-8
linode-cli ai deploy --wait

# Development
linode-cli ai init llm-api --directory dev
cd dev
nano deploy.yml  # region: us-southeast, type: g6-standard-4
linode-cli ai deploy --wait
```

### Create Your Own Template

Use AI assistance to scaffold a new template:

```bash
# Create template with LLM assistance
linode-cli ai templates scaffold my-api --llm-assist

# Answer a few questions, then feed to your LLM:
# "@my-api/llm-instructions.md complete this template"

# Validate and test
linode-cli ai templates validate my-api
linode-cli ai templates test my-api --dry-run

# Deploy
linode-cli ai init my-api --directory test-deploy
cd test-deploy
linode-cli ai deploy --wait
```

---

## 📖 How It Works

### Template Authoring

Templates are defined in `template.yml` files:

```yaml
name: my-api
display_name: My API
version: 1.0.0

description: |
  My awesome AI service

capabilities:
  runtime: docker
  features:
    - gpu-nvidia        # NVIDIA GPU support
    - docker-optimize   # Fast image pulls

deploy:
  target: linode
  linode:
    image: linode/ubuntu22.04
    region_default: us-mia
    type_default: g6-standard-8
    
    container:
      image: myorg/myapi:latest
      internal_port: 8000
      external_port: 80
      
      health:
        type: http
        path: /health
        port: 8000
```

### Deployment Configuration

When you run `init`, the template is copied to `deploy.yml` in your deployment directory. You can then customize it for each deployment:

```
my-deployment/
├── deploy.yml        # Complete deployment config (customize this!)
├── .env              # Your secrets
├── .env.example      # Template
└── README.md         # Usage instructions
```

### Single Source of Truth

Everything you need is in `deploy.yml`:
- **What to deploy**: Container image, ports, capabilities
- **Where to deploy**: Region, instance type, OS image
- **How to configure**: Environment vars, health checks, startup commands

Customize once, deploy anywhere!

---

## 🔧 Configuration

Plugin config is stored at `~/.config/linode-cli.d/ai/config.yml`:

```yaml
templates:
  registry_url: https://raw.githubusercontent.com/linode/linode-cli-ai-templates/main/index.yml
  cache_dir: ~/.config/linode-cli.d/ai/templates
  auto_update: true
  update_check_interval: 86400  # 24 hours
```

Deployments are tracked at `~/.config/linode-cli.d/ai/ai-deployments.json`.

---

## 📚 Documentation

- **[Template Development Guide](docs/template-development.md)** - Create custom templates
- **[Template Deployment Guide](docs/template-deployments.md)** - Deep dive into deployments
- **[Quick Reference](docs/template-quick-reference.md)** - Common patterns and examples
- **[Community Templates](https://github.com/linode/linode-cli-ai-templates)** - Browse and contribute

---

## 🤝 Contributing

We welcome contributions! Here's how you can help:

### Share Your Templates

1. Fork the [template repository](https://github.com/linode/linode-cli-ai-templates)
2. Create your template following the [development guide](docs/template-development.md)
3. Submit a pull request

### Report Issues

Found a bug? Have a feature request? [Open an issue](https://github.com/linode/linode-cli-ai/issues)!

### Improve Documentation

Documentation PRs are always welcome!

---

## 📝 License

[Apache 2.0](LICENSE)

---

## 🙏 Acknowledgments

Built with ❤️ for the AI and cloud computing community.

Powered by [Linode](https://www.linode.com/) cloud infrastructure.

---

**Ready to deploy?** Start with `linode-cli ai templates list` and see what you can build! 🚀
