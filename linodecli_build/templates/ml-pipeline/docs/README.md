# ML Pipeline Template

Production ML inference pipeline with GPU support, caching, and monitoring.

## Overview

This template provides a **starter framework** for deploying ML models on Linode. It includes:

- **PyTorch** container with CUDA support
- **FastAPI** for REST API endpoints
- **Redis** for caching inference results
- **Prometheus** metrics for monitoring
- **NVIDIA GPU** support (RTX 4000 Ada by default)
- **BuildWatch** for deployment monitoring

**Important**: This is a **template/scaffold** - you need to add your actual ML model code!

## What Gets Deployed

The template creates:
- A Linode GPU instance (g2-gpu-rtx4000a4-m)
- Docker container running PyTorch 2.0 with CUDA
- Redis server for caching
- FastAPI app with these endpoints:
  - `GET /health` - Health check
  - `GET /metrics` - Prometheus metrics
  - `POST /predict` - Inference endpoint (you customize this!)
  - `GET /docs` - Auto-generated API documentation

## Quick Start

### 1. Initialize the template

```bash
cd my-ml-project
linode-cli build init ml-pipeline
```

This creates:
- `deploy.yml` - Deployment configuration
- `.env.example` - Environment variables template
- `README.md` - This file

### 2. Review the configuration

Open `deploy.yml` and review:
- **Region**: Default is `us-ord` (Chicago)
- **Instance type**: Default is `g2-gpu-rtx4000a4-m` (GPU instance)
- **Container image**: PyTorch 2.0 with CUDA 11.7

You can change these settings or override them at deploy time.

### 3. Set up environment (optional)

```bash
cp .env.example .env
# Edit .env if you need to customize Redis or logging settings
```

Optional environment variables:
- `REDIS_HOST` - Redis hostname (default: localhost)
- `REDIS_PORT` - Redis port (default: 6379)
- `LOG_LEVEL` - Logging level (default: info)
- `BATCH_SIZE` - Inference batch size (default: 32)

### 4. Deploy

```bash
linode-cli build deploy
```

The deployment will:
1. Create a GPU instance
2. Install NVIDIA drivers
3. Set up Docker with GPU support
4. Install Redis
5. Pull the PyTorch container
6. Start your API server

**⏱️ First deployment takes ~10-15 minutes** (NVIDIA driver installation)

### 5. Test the deployment

Once deployed, you'll see the IP address. Test it:

```bash
# Health check
curl http://YOUR_IP/health

# API documentation
open http://YOUR_IP/docs

# Test prediction (returns placeholder for now)
curl -X POST http://YOUR_IP/predict \
  -H 'Content-Type: application/json' \
  -d '{"input": "test data"}'
```

## Customizing for Your Model

The template provides a **starting point**. Here's how to add your actual model:

### Option 1: Edit deploy.yml directly

Open `deploy.yml` and edit the `setup.files` section:

```yaml
setup:
  files:
    - path: /app/main.py
      permissions: "0644"
      content: |
        # Add your model loading and inference code here
        import torch
        from fastapi import FastAPI
        
        # Load your model
        model = torch.load('/app/my_model.pth')
        model.eval()
        
        app = FastAPI()
        
        @app.post("/predict")
        def predict(data: dict):
            # Your inference logic here
            input_tensor = preprocess(data)
            with torch.no_grad():
                output = model(input_tensor)
            return {"prediction": postprocess(output)}
```

### Option 2: Use a custom container image

Replace the container image in `deploy.yml`:

```yaml
deploy:
  linode:
    container:
      image: your-registry/your-ml-model:latest
```

### Option 3: Add model files to the container

Add your model files in `setup.files`:

```yaml
setup:
  files:
    - path: /app/model.pth
      permissions: "0644"
      content: |
        # Base64 encoded model or download script
    
    - path: /app/download_model.sh
      permissions: "0755"
      content: |
        #!/bin/bash
        wget https://your-storage.com/model.pth -O /app/model.pth
```

## Example: BERT Sentiment Analysis

Here's a complete example that adds BERT sentiment analysis:

```yaml
# In deploy.yml, edit setup.files
setup:
  files:
    - path: /app/main.py
      permissions: "0644"
      content: |
        from fastapi import FastAPI
        from transformers import pipeline
        import torch
        
        app = FastAPI()
        
        # Load BERT model
        classifier = pipeline(
            "sentiment-analysis",
            device=0 if torch.cuda.is_available() else -1
        )
        
        @app.get("/health")
        def health():
            return {"status": "healthy", "gpu": torch.cuda.is_available()}
        
        @app.post("/predict")
        def predict(data: dict):
            text = data.get("text", "")
            result = classifier(text)[0]
            return {
                "text": text,
                "sentiment": result["label"],
                "confidence": result["score"]
            }
    
    - path: /app/requirements.txt
      permissions: "0644"
      content: |
        fastapi
        uvicorn[standard]
        transformers
        torch
        accelerate
```

Then deploy:

```bash
linode-cli build deploy
```

Test it:

```bash
curl -X POST http://YOUR_IP/predict \
  -H 'Content-Type: application/json' \
  -d '{"text": "This product is amazing!"}'
```

## Using the TUI

Monitor your deployment interactively:

```bash
# Dashboard view (all deployments)
linode-cli build tui

# Status view (specific deployment)
linode-cli build tui --status
```

The TUI shows:
- Instance status
- Container health
- Real-time logs from BuildWatch
- GPU availability
- Docker layer downloads

## Common Patterns

### 1. Loading Large Models

For large models (>1GB), download them at runtime:

```yaml
setup:
  files:
    - path: /app/download_model.sh
      permissions: "0755"
      content: |
        #!/bin/bash
        echo "Downloading model..."
        wget https://huggingface.co/your-model/resolve/main/pytorch_model.bin \
          -O /app/model.bin
        echo "Model downloaded"
    
  script: |
    #!/bin/bash
    /app/download_model.sh
```

### 2. Using Hugging Face Models

```python
from transformers import AutoModelForSequenceClassification, AutoTokenizer

model_name = "bert-base-uncased"
model = AutoModelForSequenceClassification.from_pretrained(model_name)
tokenizer = AutoTokenizer.from_pretrained(model_name)

# Move to GPU
if torch.cuda.is_available():
    model = model.cuda()
```

### 3. Batch Processing

```python
@app.post("/predict")
def predict(data: dict):
    inputs = data.get("inputs", [])
    batch_size = int(os.getenv("BATCH_SIZE", 32))
    
    results = []
    for i in range(0, len(inputs), batch_size):
        batch = inputs[i:i+batch_size]
        batch_results = model(batch)
        results.extend(batch_results)
    
    return {"predictions": results}
```

### 4. Response Caching

```python
import redis
import json
import hashlib

redis_client = redis.Redis(host="localhost", port=6379)

@app.post("/predict")
def predict(data: dict):
    # Create cache key
    cache_key = hashlib.md5(json.dumps(data).encode()).hexdigest()
    
    # Check cache
    cached = redis_client.get(cache_key)
    if cached:
        return json.loads(cached)
    
    # Run inference
    result = model(data)
    
    # Cache result (expire after 1 hour)
    redis_client.setex(cache_key, 3600, json.dumps(result))
    
    return result
```

## Monitoring & Debugging

### View Logs

```bash
# Via TUI
linode-cli build tui --status

# Via SSH
./connect.sh
docker logs -f app
```

### Check GPU

```bash
./connect.sh
nvidia-smi
```

### Monitor Metrics

The `/metrics` endpoint provides Prometheus-compatible metrics:

```bash
curl http://YOUR_IP/metrics
```

## Cost Considerations

GPU instances are more expensive:

- **g2-gpu-rtx4000a4-m**: ~$1.50/hour
- Consider smaller instance types if GPU isn't required
- Destroy instances when not in use: `linode-cli build destroy`

## Troubleshooting

### GPU Not Available

Check logs for NVIDIA driver installation:
```bash
./connect.sh
journalctl -u cloud-final
```

### Container Won't Start

Check Docker logs:
```bash
./connect.sh
docker logs app
```

### Out of Memory

Reduce batch size in `.env`:
```bash
BATCH_SIZE=8
```

## Next Steps

1. **Add your model** - Edit `deploy.yml` to include your model code
2. **Test locally** - Test your inference logic before deploying
3. **Deploy** - Run `linode-cli build deploy`
4. **Monitor** - Use the TUI or check logs
5. **Iterate** - Update `deploy.yml` and redeploy as needed

## Related Templates

- `llm-api` - For LLM inference (vLLM-based)
- `embeddings-python` - For embeddings generation
- `chat-agent` - For chat applications (Ollama-based)

## Support

- [Documentation](https://github.com/mighteejim/linode-cli-build/blob/main/docs/GUIDE.md)
- [Template Development Guide](https://github.com/mighteejim/linode-cli-build/blob/main/docs/TEMPLATES.md)
- [Capabilities Reference](https://github.com/mighteejim/linode-cli-build/blob/main/docs/CAPABILITIES.md)
