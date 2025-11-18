# Embeddings (Python) Template

Python-based alternative to the TEI (Rust) embeddings server. Uses the same `sentence-transformers` model but avoids the hf-hub Rust library issues.

## Why Use This Instead of TEI?

- ✅ **Reliable**: No Rust/hf-hub endpoint configuration issues
- ✅ **Compatible**: Same API interface as TEI
- ✅ **Flexible**: Easy to customize and debug
- ✅ **Works everywhere**: No architecture-specific binaries

## Defaults

| Setting | Value |
| --- | --- |
| Base image | `linode/ubuntu24.04` |
| Region (default) | `us-southeast` |
| Linode type (default) | `g6-standard-2` |
| Container image | `python:3.11-slim` |
| External port | `80` |
| Health check | `http://<host>/health` |

## Usage

```bash
linode-cli ai init embeddings-python --directory embeddings-demo
cd embeddings-demo
linode-cli ai deploy --region us-southeast --linode-type g6-standard-2 --wait
linode-cli ai status
```

## API Compatibility

This template provides the same API as TEI:

### Health Check
```bash
curl http://<host>/health
```

### Generate Embeddings
```bash
curl -X POST http://<host>/embed \
  -H "Content-Type: application/json" \
  -d '{"inputs":["Hello from Linode", "Another sentence"]}'
```

Returns:
```json
[
  [-0.0123, 0.0456, ...],  // 768-dimensional vector for first input
  [-0.0789, 0.0234, ...]   // 768-dimensional vector for second input
]
```

## Performance

- **Startup time**: ~60-90 seconds (downloads model + installs deps)
- **First request**: ~1-2 seconds (model already loaded)
- **Subsequent requests**: ~100-200ms per sentence

## Advantages Over TEI

1. **No hf-hub issues**: Uses Python's `huggingface_hub` which is more mature
2. **Easy debugging**: Python stack traces are clearer
3. **Customizable**: Easy to add features (batching, caching, etc.)
4. **Reliable**: Proven Python ecosystem

## Limitations

- Slightly slower than optimized TEI (but still very fast)
- Uses more memory (~1.5GB vs ~800MB for TEI)
- No GPU support in this template (can be added)

## Cleanup

```bash
linode-cli ai destroy --app embeddings-python --env default
```
