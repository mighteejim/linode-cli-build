# LLM API Template

Deploys [`vllm/vllm-openai:latest`](https://hub.docker.com/r/vllm/vllm-openai) to expose an OpenAI-compatible HTTP endpoint backed by vLLM.

**⚠️ GPU Required**: This template requires a GPU-enabled Linode instance (g6-standard-8 or higher) with Ubuntu 22.04.

## Defaults

| Setting | Value |
| --- | --- |
| Base image | `linode/ubuntu22.04` |
| Region (default) | `us-mia` |
| Linode type (default) | `g6-standard-8` (GPU) |
| Container image | `vllm/vllm-openai:latest` |
| External port | `80` (forwarded to `8000`) |
| Health check | `http://<hostname>/health` |

## What Gets Deployed

When you deploy this template, cloud-init automatically:

1. Installs Docker with optimized download settings (10 concurrent layer downloads)
2. **Installs NVIDIA drivers (535)** for GPU access
3. **Installs NVIDIA Container Toolkit** for Docker GPU support
4. Pulls the vLLM container image (parallelized for faster downloads)
5. Starts the container with `--gpus all` flag
6. Downloads the specified model (default: Meta-Llama-3-8B-Instruct)

## Environment Variables

| Variable | Required | Description |
| --- | --- | --- |
| `HF_TOKEN` | **Yes** | Hugging Face token with access to the model you want to deploy. |
| `MODEL_NAME` | No | HuggingFace model to load (default: `meta-llama/Meta-Llama-3-8B-Instruct`). |
| `MAX_MODEL_LEN` | No | Maximum model context length (default: `16384`). |
| `VLLM_GPU_MEMORY_UTILIZATION` | No | GPU memory utilization fraction (default: `0.9`). |

### Popular Models

You can override `MODEL_NAME` in your `.env` file to use different models:

```bash
# Open-source alternatives that don't require gating
MODEL_NAME=microsoft/Phi-3-mini-4k-instruct
MODEL_NAME=mistralai/Mistral-7B-Instruct-v0.3
MODEL_NAME=Qwen/Qwen2.5-7B-Instruct

# Gated models (require HF access approval)
MODEL_NAME=meta-llama/Meta-Llama-3-8B-Instruct
MODEL_NAME=meta-llama/Meta-Llama-3-70B-Instruct
```

**Note:** Larger models (13B+) require larger instance types with more GPU memory.

## Usage

```bash
linode-cli ai init llm-api --directory llm-demo
cd llm-demo
cp .env.example .env

# Edit .env file with your settings
cat >> .env <<EOF
HF_TOKEN=hf_xxx
MODEL_NAME=meta-llama/Meta-Llama-3-8B-Instruct
EOF

linode-cli ai deploy --region us-mia --linode-type g6-standard-8 --image linode/ubuntu22.04 --wait
```

**Note**: Always use `linode/ubuntu22.04` for GPU instances to ensure proper NVIDIA driver installation.

### Deployment Time

**Total deployment time**: ~4-8 minutes (optimized)
- Instance provisioning: ~1 minute  
- NVIDIA driver installation: ~2-3 minutes
- Docker + NVIDIA Container Toolkit: ~1 minute
- vLLM container pull: ~1-2 minutes (parallelized downloads)
- Model download (first run): ~1-2 minutes

The deployment now uses parallel layer downloads (10 concurrent) for faster container image pulls. The health check will automatically wait up to 10 minutes for the service to be ready.

### Check Status

```bash
linode-cli ai status
```

Health will pass once `http://<hostname>/health` responds with HTTP 200.

### Test the API

```bash
# Get the hostname from status output
HOSTNAME=$(linode-cli ai status --format json | jq -r '.hostname')

# List models
curl http://$HOSTNAME/v1/models

# Generate text
curl -X POST http://$HOSTNAME/v1/completions \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "meta-llama/Meta-Llama-3-8B-Instruct",
    "prompt": "Once upon a time",
    "max_tokens": 50
  }'

# Chat completion (OpenAI-compatible)
curl -X POST http://$HOSTNAME/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "meta-llama/Meta-Llama-3-8B-Instruct",
    "messages": [{"role": "user", "content": "What is AI?"}],
    "max_tokens": 100
  }'
```

### Clean Up

Destroy when finished:

```bash
linode-cli ai destroy --app llm-api --env default
```

## Troubleshooting

### Container fails with "libcuda.so.1: cannot open shared object file"

This error means the NVIDIA drivers or Container Toolkit weren't installed properly. This should now be automatically handled by the updated template.

If you're using an older deployment, SSH into your Linode and run:

```bash
# Check if GPU is detected
lspci | grep -i nvidia

# Check if NVIDIA drivers are installed
nvidia-smi

# Check Docker GPU support
docker run --rm --gpus all nvidia/cuda:12.0-base nvidia-smi
```

### Model download fails

Make sure your `HF_TOKEN` has access to the model. For Meta Llama models, you need to:
1. Accept the license on Hugging Face
2. Generate an access token with read permissions

### Out of memory errors

Try a larger instance type (g6-dedicated-16 or higher) or set `VLLM_GPU_MEMORY_UTILIZATION` to a lower value (e.g., 0.8).

## Instance Sizing

| Instance Type | vCPU | RAM | GPU | Best For |
|--------------|------|-----|-----|----------|
| g6-standard-4 | 4 | 16GB | 1x RTX 6000 Ada | Small models (< 7B params) |
| g6-standard-8 | 8 | 32GB | 1x RTX 6000 Ada | Medium models (7-13B params) |
| g6-dedicated-16 | 16 | 64GB | 1x RTX 6000 Ada | Large models (13-30B params) |

## Performance

With the default configuration (Llama-3-8B):
- First token latency: ~200-500ms
- Throughput: ~50-100 tokens/second
- Concurrent requests: 5-10 (depending on sequence length)

## Cost Estimates

| Instance Type | Hourly | Monthly (730hrs) |
|--------------|--------|------------------|
| g6-standard-8 | $1.50 | ~$1,095 |
| g6-dedicated-16 | $3.00 | ~$2,190 |

💡 **Tip**: Use the instance for development/testing, then destroy it when not in use to save costs.
