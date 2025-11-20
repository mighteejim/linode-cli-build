# 🚀 linode-cli build

**Deploy applications to Linode in minutes with simple, declarative templates.**

A `linode-cli` plugin that makes deploying applications as easy as running a single command. Perfect for LLM APIs, chat agents, embeddings servers, web services, and more.

---

## ✨ Features

- 🎯 **Simple Workflow** - Init, customize, deploy. That's it.
- 🚀 **Ready-to-Use Templates** - Pre-configured for common workloads including AI/ML
- 📦 **Template System** - Use bundled templates or create your own
- 🔧 **Fully Customizable** - Override any setting per deployment
- 🌐 **Multi-Environment** - Deploy prod, staging, dev from the same template
- 🏥 **Health Checks** - Automatic health monitoring for your services
- 📊 **Status Tracking** - See all deployments and their health at a glance

---

## 📦 Installation

```bash
pip install linodecli-build
linode-cli register-plugin linodecli_build
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
linode-cli register-plugin linodecli_build
```

---

## 🚀 Quick Start

Deploy an LLM API in under 2 minutes:

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

That's it! Your LLM API is now running on Linode with GPU support.

---

## 📚 Commands Reference

### Template Management

| Command | Description |
|---------|-------------|
| `linode-cli build templates list` | 📋 List bundled and user templates |
| `linode-cli build templates show <name>` | 🔍 Show template details |
| `linode-cli build templates scaffold <name>` | ✏️ Create a new template |
| `linode-cli build templates validate <path>` | ✅ Validate template syntax |
| `linode-cli build templates install <path>` | 💾 Install local template for reuse |
| `linode-cli build templates uninstall <name>` | 🗑️ Remove installed template |

### Deployment Lifecycle

| Command | Description |
|---------|-------------|
| `linode-cli build init <template>` | 🎬 Initialize a new deployment |
| `linode-cli build deploy` | 🚀 Deploy to Linode |
| `linode-cli build status` | 📊 Check deployment status |
| `linode-cli build destroy` | 💣 Tear down deployment |

### Interactive TUI (Terminal UI)

| Command | Description |
|---------|-------------|
| `linode-cli build tui` | 📊 Launch dashboard (default view) |
| `linode-cli build tui deploy` | 📺 Monitor deployment progress in real-time |
| `linode-cli build tui status` | 🖥️ View live status dashboard |

---

## 📺 Interactive TUI

Monitor deployments in real-time with the interactive Terminal User Interface:

```bash
# Launch the dashboard (shows all deployments)
linode-cli build tui

# Monitor deployment progress with live updates
cd my-project
linode-cli build tui deploy

# View live status dashboard
linode-cli build tui status --app my-app
```

### TUI Features

- 📊 **Dashboard** - Central view of all your deployments
  - Lists all deployments in current directory
  - Shows instance IDs and status at a glance
  - Navigate with arrow keys, select with Enter
  - Auto-discovers deployments in subdirectories

- 🎬 **Live Deployment Monitor** - Watch deployment progress in real-time
  - Progress bar with stage tracking
  - Live cloud-init output streaming
  - Instance details and status
  - Elapsed time tracking

- 📊 **Status Dashboard** - Monitor your deployed applications
  - Real-time instance and container status
  - Auto-refresh every 5 seconds
  - Health check monitoring
  - Recent activity logs
  - Quick actions (SSH, Destroy)

### Keyboard Shortcuts

| Key | Action |
|-----|--------|
| `↑↓` / `j/k` | Navigate (dashboard) |
| `Enter` | Select deployment (dashboard) |
| `Esc` / `Ctrl+C` | Exit |
| `R` | Refresh |
| `S` | Show SSH command (status view) |
| `D` | Destroy deployment (status view) |
| `?` | Show help |

The TUI provides a much richer monitoring experience compared to the CLI, perfect for watching long-running deployments or keeping an eye on production services.

---

## 🎨 Available Templates

### Bundled Templates

| Template | Description | GPU |
|----------|-------------|-----|
| **chat-agent** | Ollama-based chat agent with Llama 3 | ✅ |
| **llm-api** | vLLM text generation API (OpenAI-compatible) | ✅ |
| **embeddings-python** | Sentence-transformers embeddings server | ❌ |
| **ml-pipeline** | Production ML inference with batching, caching & monitoring | ✅ |

---

## 💡 Example Workflows

### Deploy Multiple Environments

Use the same template for different environments:

```bash
# Production
linode-cli build init llm-api --directory prod
cd prod
nano deploy.yml  # region: us-east, type: g6-dedicated-16
linode-cli build deploy --wait

# Staging
linode-cli build init llm-api --directory staging
cd staging
nano deploy.yml  # region: us-west, type: g6-standard-8
linode-cli build deploy --wait

# Development
linode-cli build init llm-api --directory dev
cd dev
nano deploy.yml  # region: us-southeast, type: g6-standard-4
linode-cli build deploy --wait
```

### Create Your Own Template

Use AI assistance to scaffold a new template:

```bash
# Create template with LLM assistance
linode-cli build templates scaffold my-api --llm-assist

# Answer a few questions, then feed to your LLM:
# "@my-api/llm-instructions.md complete this template"

# Validate
linode-cli build templates validate my-api

# Test locally
linode-cli build init ./my-api --directory test-deploy
cd test-deploy
linode-cli build deploy --wait

# Install for reuse (once you're happy with it)
cd ..
linode-cli build templates install ./my-api

# Now use it like a bundled template
linode-cli build init my-api --directory production
cd production
linode-cli build deploy
```

Your installed templates are stored at `~/.config/linode-cli.d/build/templates/` and won't be overwritten during plugin upgrades.

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

---

## 📚 Documentation

- **[Capabilities Reference](docs/capabilities.md)** - Complete guide to all capabilities (GPU, Docker, Redis, BuildWatch, etc.)
- **[Template Development Guide](docs/template-development.md)** - Create custom templates
- **[Template Deployment Guide](docs/template-deployments.md)** - Deep dive into deployments
- **[Quick Reference](docs/template-quick-reference.md)** - Common patterns and examples
- **[Community Templates](https://github.com/linode/linode-cli-ai-templates)** - Browse and contribute

---

## 🤝 Contributing

We welcome contributions! Here's how you can help:

### Add New Templates

1. Fork this repository
2. Create your template in `linodecli_build/templates/your-template/`
3. Add to `linodecli_build/templates/index.yml`
4. Submit a pull request

Use `linode-cli build templates scaffold` to help create your template.

### Report Issues

Found a bug? Have a feature request? [Open an issue](https://github.com/linode/linode-cli-build/issues)!

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

**Ready to deploy?** Start with `linode-cli build templates list` and see what you can build! 🚀
