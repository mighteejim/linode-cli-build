# Chat Agent Template

Runs [`ollama/ollama:latest`](https://hub.docker.com/r/ollama/ollama) on a
single Linode. Cloud-init installs Docker, pulls the image, exposes port 80,
and runs an optional post-start hook to preload a model.

## Defaults

| Setting | Value |
| --- | --- |
| Base image | `linode/ubuntu24.04` |
| Region (default) | `us-chi` |
| Linode type (default) | `g6-standard-2` |
| Container image | `ollama/ollama:latest` |
| External port | `80` (forwarded to `11434`) |
| Health check | `http://<hostname>:11434/api/tags` |

## Environment Variables

`.env.example` is empty because no secrets are required, but you can set:

| Variable | Required | Description |
| --- | --- | --- |
| `OLLAMA_MODELS` | No | Comma-separated list of models to pull after startup (e.g. `llama3`); used by the post-start hook. |

Add your own application-specific variables as needed—they will be present in
the container’s environment.

## Usage

```bash
linode-cli ai init chat-agent --directory chat-demo
cd chat-demo
cp .env.example .env  # add OLLAMA_MODELS if desired
linode-cli ai deploy --region us-chi --linode-type g6-standard-2 --wait
linode-cli ai status
```

Once running, access the Ollama API at `http://<hostname>/api/tags` (80→11434).
Destroy the deployment when finished:

```bash
linode-cli ai destroy --app chat-agent --env default
```
