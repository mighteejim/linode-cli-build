# LLM API Template

Deploys [`vllm/vllm-openai:latest`](https://hub.docker.com/r/vllm/vllm-openai)
to expose an OpenAI-compatible HTTP endpoint backed by vLLM.

## Defaults

| Setting | Value |
| --- | --- |
| Base image | `linode/ubuntu24.04` |
| Region (default) | `us-mia` |
| Linode type (default) | `g6-standard-8` |
| Container image | `vllm/vllm-openai:latest` |
| External port | `80` (forwarded to `8000`) |
| Health check | `http://<hostname>:8000/health` |

## Environment Variables

| Variable | Required | Description |
| --- | --- | --- |
| `HF_TOKEN` | **Yes** | Hugging Face token with access to the specified model (defaults to `meta-llama/Meta-Llama-3-8B-Instruct`). |
| `VLLM_GPU_MEMORY_UTILIZATION` | No | Override GPU memory utilization fraction (stringified float). |

You may also override `MODEL_NAME` by editing `ai.linode.yml` or providing an
env var; the template sets `MODEL_NAME` via the container defaults.

## Usage

```bash
linode-cli ai init llm-api --directory llm-demo
cd llm-demo
cp .env.example .env
echo "HF_TOKEN=hf_xxx" >> .env
linode-cli ai deploy --region us-mia --linode-type g6-standard-8 --wait
linode-cli ai status
```

Health will pass once `http://<hostname>/health` responds with HTTP 200. Destroy
when finished:

```bash
linode-cli ai destroy --app llm-api --env default
```
