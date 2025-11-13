# Phase 1: `linode-cli ai` Plugin – Implementation Instructions

You are a code-focused assistant (GPT Codex) helping implement a new plugin for the Linode CLI called `ai`. This document defines the **requirements, architecture, and tasks** for Phase 1.

The goal:  
> Provide a developer-friendly `linode-cli ai` plugin that can deploy **AI demo apps** on Linode using **public container images** and **cloud-init**, with **no separate orchestrator service** and **no custom registry**.

---

## 1. High-Level Overview

We want a new plugin for the existing `linode-cli`:

```bash
linode-cli ai ...
```

The plugin will:

- Use the **existing Linode CLI auth/config** (no separate credentials).
- Support **single-Linode deployments** only in v1 (no LKE yet).
- Deploy apps using **public Docker images** (Ollama, vLLM, etc.).
- Use **cloud-init** on the created Linode instance to:
  - Install Docker
  - Pull the public image
  - Run the container
- Track deployments locally in a small **JSON registry**.
- Use the default **Linode hostname** like `45-33-68-91.ip.linodeusercontent.com`.

There is **no separate control-plane or orchestrator server** in Phase 1.

---

## 2. Plugin Architecture & Project Layout

### 2.1 Python package

Create a Python package for the plugin, something like:

- Package name: `linodecli_ai`
- Main module: `linodecli_ai/__init__.py`

The plugin must expose a `populate(subparsers, config)` function that the main `linode-cli` can call (follow the Linode CLI plugin API contract).

Example skeleton:

```python
# linodecli_ai/__init__.py

def populate(subparsers, config):
    # Called by linode-cli to register this plugin.
    # - subparsers: argparse subparsers from the main CLI.
    # - config: linode-cli config object (for auth, defaults, etc.).
    # define `ai` command & its subcommands here
    ...
```

### 2.2 File layout

Suggested layout:

```text
linodecli_ai/
  __init__.py          # plugin entrypoint (populate)
  commands/
    __init__.py
    templates.py       # templates list/show
    init.py            # project init
    deploy.py          # deploy logic
    status.py          # status
    destroy.py         # destroy
  core/
    templates.py       # template loading/parsing
    cloud_init.py      # cloud-init generation
    registry.py        # local deployment registry
    linode_api.py      # thin wrapper around linode-cli client
    env.py             # env var handling
  templates/
    index.yml          # template index
    chat-agent/template.yml
    llm-api/template.yml
    ...                # more templates later
pyproject.toml / setup.cfg / setup.py
README.md
```

You don’t have to match this exactly, but keep **command vs core logic** separated.

---

## 3. Commands & UX Requirements

### 3.1 Top-level `ai` command

When a user runs:

```bash
linode-cli ai --help
```

They should see something like:

```text
Usage: linode-cli ai [COMMAND] [ARGS...]

Commands:
  templates   List and inspect AI templates
  init        Initialize a local project from a template
  deploy      Deploy the current AI project to Linode
  status      Show status of deployments
  destroy     Destroy a deployment and its Linode
```

### 3.2 Subcommands

#### 3.2.1 `linode-cli ai templates list`

- Reads the local `templates/index.yml`.
- Prints a table of templates with:
  - `name`
  - `version`
  - short `description`

Example:

```text
NAME         VERSION  DESCRIPTION
chat-agent   0.1.0    Basic chat agent using Ollama (public image).
llm-api      0.1.0    OpenAI-compatible LLM API using vLLM.
embeddings   0.1.0    Embeddings server using TEI.
```

#### 3.2.2 `linode-cli ai templates show <name>`

- Shows detailed info from the template file.
- Should print:
  - Name, version, description
  - Default region/type
  - Container image
  - Health check path/port
  - Required env vars

#### 3.2.3 `linode-cli ai init <template> [--directory DIR]`

- Creates a **local project directory** for the given template.

Behavior:

- If `--directory` is provided:
  - Create the directory (or fail if non-empty).
  - Write files inside it.
- If not provided:
  - Use the current working directory (fail if `ai.linode.yml` already exists).

Files to create:

1. `ai.linode.yml` — project manifest (see format below).
2. `.env.example` — stub env file if the template defines required env vars.
3. Optional `README.md` with a short description and quickstart notes.

Example `ai.linode.yml`:

```yaml
template:
  name: chat-agent
  version: 0.1.0
deploy:
  region: us-chi
  linode_type: g6-standard-2
  app_name: chat-agent
  env: default
env:
  file: .env
```

#### 3.2.4 `linode-cli ai deploy [--region REGION] [--linode-type TYPE] [--env-file PATH] [--image IMAGE] [--app-name NAME] [--env ENV]`

- Deploys the current project (based on `ai.linode.yml` and template definition).
- Must be run **inside** a project directory (where `ai.linode.yml` exists).

Behavior:

1. Load `ai.linode.yml`.
2. Load the corresponding template file.
3. Validate env vars:
   - Read env file (from `ai.linode.yml` or `--env-file`).
   - Ensure required env vars defined in template are present.
4. Resolve deployment settings:
   - Region: `--region` or project or template default.
   - Linode type: `--linode-type` or project or template default.
   - App name: `--app-name` or project default.
   - Env name: `--env` or `default`.
   - Container image: `--image` or template container image.
5. Generate **cloud-init** user data via `core/cloud_init.py`.
6. Call **Linode API** to create a new Linode with:
   - Region, type, base image (e.g. `linode/ubuntu24.04`).
   - `user_data`: cloud-init YAML.
   - Label: e.g. `build-ai-<app_name>-<env>-<timestamp>`.
   - Tags:

     ```text
     build_ai_app=<app_name>
     build_ai_env=<env>
     build_ai_template=<template_name>
     build_ai_template_version=<template_version>
     build_ai_deployment_id=<uuid>
     ```

7. Read back Linode details:
   - `linode_id`
   - `ipv4` (e.g., `45.33.68.91`)
8. Derive a hostname:
   - `45-33-68-91.ip.linodeusercontent.com`
9. Write **deployment record** into the local registry JSON file.
10. Optionally wait for the Linode to reach `running` state and perform a health check (HTTP).
11. Print deployment info:

```text
Deployed chat-agent (env: default)

Status: provisioning
Linode ID: 123456
Region: us-chi
URL:    http://45-33-68-91.ip.linodeusercontent.com

Run `linode-cli ai status` to check when it's ready.
```

*(If health checking is implemented inline, you can print `Status: running` when health passes.)*

#### 3.2.5 `linode-cli ai status [--app NAME] [--env ENV] [--verbose]`

- Shows deployment status combining local registry + Linode API + health check.

Behavior:

1. Load local registry JSON.
2. Filter by `app_name` and `env` if provided; otherwise show all.
3. For each deployment:
   - Call Linode API to get instance status.
   - If `status != running`:
     - Map to human status:
       - `booting/creating` → `provisioning`
       - `offline` → `stopped`
       - `missing` → `missing` (if 404).
   - If `status == running`:
     - Optionally perform HTTP health check using template’s health config:
       - Health URL: `http://<hostname>:<health.port><health.path>`
       - 2xx → `running`
       - otherwise → `degraded`.
4. Print a table:

```text
APP         ENV      REGION  STATUS      URL
chat-agent  default  us-chi  running     http://45-33-68-91.ip.linodeusercontent.com
```

If `--verbose` is set, print more details (linode_id, last health check, etc.).

#### 3.2.6 `linode-cli ai destroy [--app NAME] [--env ENV]`

- Deletes the Linode for the selected deployment(s) and removes them from local registry.

Behavior:

1. Load local registry.
2. Filter by `--app` and `--env` if present; otherwise:
   - If only one deployment exists, target that.
   - If multiple and args are ambiguous, ask for clarification or require flags.
3. Show what will be destroyed and prompt for confirmation.
4. Call Linode API to delete each referenced Linode.
5. Remove those deployments from local registry JSON.
6. Print a summary.

---

## 4. Template System (Using Public Images)

### 4.1 Template index (`templates/index.yml`)

Create a YAML file listing templates:

```yaml
templates:
  - name: chat-agent
    path: templates/chat-agent/template.yml
  - name: llm-api
    path: templates/llm-api/template.yml
  - name: embeddings
    path: templates/embeddings/template.yml
```

`templates list/show` commands will read this file.

### 4.2 Template definition (`templates/<name>/template.yml`)

Each template YAML should define:

- Metadata
- Deployment defaults
- Container config
- Health check
- Required env vars (if any)

Example: **`chat-agent`** template using `ollama/ollama`:

```yaml
name: chat-agent
display_name: Chat Agent
version: 0.1.0

description: >
  Basic LLM chat agent using the public Ollama image.

deploy:
  target: linode

  linode:
    region_default: us-chi
    type_default: g6-standard-2

    container:
      image: ollama/ollama:latest
      internal_port: 11434
      external_port: 80

      # optional script to run after container starts
      post_start_script: |
        #!/bin/bash
        docker exec app ollama pull llama3

      health:
        type: http
        path: /api/tags
        port: 11434
        success_codes: [200]
        initial_delay_seconds: 10
        timeout_seconds: 2
        max_retries: 30

env:
  required: []
  optional: []
```

Add at least 2–3 templates of this form for demonstration:

- `chat-agent` (Ollama)
- `llm-api` (vLLM or TGI)
- `embeddings-bert` (Hugging Face TEI for embeddings)

---

## 5. Project Manifest (`ai.linode.yml`)

When `ai init` runs, it creates this file to remember project settings.

Minimum fields:

```yaml
template:
  name: chat-agent
  version: 0.1.0

deploy:
  region: us-chi
  linode_type: g6-standard-2
  app_name: chat-agent
  env: default

env:
  file: .env
```

The deploy command will:

- Use `deploy.region` and `deploy.linode_type` **unless overridden** by flags.
- Use `deploy.app_name` and `deploy.env` for tagging & display.
- Use `env.file` when reading env vars.

---

## 6. Cloud-init Generation

Create a module `core/cloud_init.py` with a function like:

```python
def generate_cloud_init(config) -> str:
    # Given:
    #   - container image
    #   - internal/external ports
    #   - env vars
    #   - optional post_start_script
    # Returns:
    #   - cloud-init user_data as a YAML string
    ...
```

### 6.1 Inputs

- `image`: container image, e.g. `ollama/ollama:latest`
- `internal_port`: e.g. `11434`
- `external_port`: e.g. `80`
- `env_vars`: dict of env key → value
- `post_start_script`: optional script (string) from template
- (future: maybe extra things, but keep v1 simple)

### 6.2 Cloud-init behavior

The generated cloud-init should:

1. Install Docker (or Podman, but Docker is fine for v1).
2. Write an env file `/etc/build-ai.env` with provided env vars.
3. Write a startup script `/usr/local/bin/start-container.sh` that:
   - Pulls the image.
   - Removes any existing container named `app`.
   - Runs the container with:
     - `--env-file /etc/build-ai.env`
     - `-p <external_port>:<internal_port>`
   - Executes `post_start_script` if provided.
4. Run `start-container.sh` via `runcmd`.

Example cloud-init YAML (simplified):

```yaml
#cloud-config
package_update: true
packages:
  - docker.io

write_files:
  - path: /etc/build-ai.env
    permissions: '0600'
    owner: root:root
    content: |
      OPENAI_API_KEY=foo
      OTHER_KEY=bar

  - path: /usr/local/bin/start-container.sh
    permissions: '0755'
    owner: root:root
    content: |
      #!/bin/bash
      set -e

      docker pull ollama/ollama:latest

      docker rm -f app || true

      docker run -d         --name app         --restart unless-stopped         --env-file /etc/build-ai.env         -p 80:11434         ollama/ollama:latest

      # post-start hook (if set)
      docker exec app ollama pull llama3

runcmd:
  - [ bash, /usr/local/bin/start-container.sh ]
```

The generator should properly indent YAML and escape env values.

---

## 7. Local Deployment Registry

Create a module `core/registry.py` to read/write a JSON file that tracks deployments.

Path (suggested):

- On Unix: `~/.config/linode-cli/ai-deployments.json`
- Use a helper function to compute this path.

Structure:

```json
{
  "deployments": [
    {
      "deployment_id": "uuid-1234",
      "app_name": "chat-agent",
      "env": "default",
      "template": "chat-agent",
      "template_version": "0.1.0",
      "target": "linode",
      "region": "us-chi",
      "linode_id": 123456,
      "ipv4": "45.33.68.91",
      "hostname": "45-33-68-91.ip.linodeusercontent.com",
      "health": {
        "http_path": "/api/tags",
        "port": 11434
      },
      "created_at": "2025-11-13T14:02:22Z",
      "last_status": "provisioning"
    }
  ]
}
```

Registry operations needed:

- `load_registry() -> dict`
- `save_registry(data: dict) -> None`
- `add_deployment(record: dict) -> None`
- `update_deployment_status(deployment_id, status) -> None`
- `remove_deployment(deployment_id) -> None`
- Helpers to filter by `app_name` & `env`.

---

## 8. Linode API Abstraction

Create `core/linode_api.py` to isolate Linode API calls.

You can:

- Use whatever client the main `linode-cli` exposes to plugins (via `config` or helper modules).
- Or shell out to `linode-cli` itself as a last resort (less ideal but acceptable as PoC).

Functions needed:

- `create_instance(region, linode_type, label, tags, user_data) -> dict`
  - Returns: at least `id`, `ipv4`, `status`.
- `get_instance(instance_id) -> dict`
  - Returns full instance info (status, ipv4, etc.).
- `delete_instance(instance_id) -> None`

Status mapping:

- If instance `status` in API is not `running`, report accordingly in `ai status`.

For hostname derivation:

- If the API exposes a reverse DNS/hostname with `ip.linodeusercontent.com`, use that.
- Otherwise, derive name from IP:

  - `45.33.68.91` → `45-33-68-91.ip.linodeusercontent.com`

---

## 9. Non-Goals for Phase 1

Explicitly **out of scope** for this implementation:

- No LKE / Kubernetes support.
- No multi-node deployments.
- No rolling updates / blue-green deploys.
- No centralized dashboard or web control-plane.
- No custom container registry.
- No advanced logs streaming (beyond what you might add later).

---

## 10. Acceptance Criteria

A Phase 1 prototype is “done” when all of this works:

1. Install plugin and register it:
   ```bash
   pip install linodecli-ai
   linode-cli register-plugin linodecli_ai
   ```
2. List templates:
   ```bash
   linode-cli ai templates list
   ```
   → Shows at least `chat-agent`.
3. Create a project:
   ```bash
   mkdir my-agent
   cd my-agent
   linode-cli ai init chat-agent
   ```
   → Creates `ai.linode.yml` and `.env.example`.
4. Deploy:
   ```bash
   cp .env.example .env  # if applicable
   linode-cli ai deploy --region us-chi --linode-type g6-standard-2
   ```
   → Creates a Linode, runs the public container, writes registry.
5. Check status:
   ```bash
   linode-cli ai status
   ```
   → Shows the app as `provisioning` and eventually `running`, with URL using `ip.linodeusercontent.com`.
6. Destroy:
   ```bash
   linode-cli ai destroy --app chat-agent --env default
   ```
   → Destroys the Linode and removes the registry entry.

If you need to choose **one template to fully wire first**, use `chat-agent` with `ollama/ollama:latest`.
