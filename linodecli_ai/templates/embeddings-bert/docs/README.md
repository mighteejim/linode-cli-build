# Embeddings (MPNet) Template

Deploys Hugging Face Text Embeddings Inference (TEI) using the
`sentence-transformers/all-mpnet-base-v2` model. Great for semantic search,
vector databases, or lightweight RAG experiments.

## Defaults

| Setting | Value |
| --- | --- |
| Base image | `linode/ubuntu24.04` |
| Region (default) | `us-southeast` |
| Linode type (default) | `g6-standard-2` |
| Container image | `ghcr.io/huggingface/text-embeddings-inference:cpu-0.4` |
| External port | `80` (maps to TEI port `3000`) |
| Health check | `http://<host>:3000/health` |

## Environment Variables

| Variable | Required | Description |
| --- | --- | --- |
| `HF_TOKEN` | No | Hugging Face token, required only if you use a gated/private model. |

## Usage

```bash
linode-cli ai init embeddings-bert --directory embeddings-demo
cd embeddings-demo
cp .env.example .env  # add HF_TOKEN if needed
linode-cli ai deploy --region us-southeast --linode-type g6-standard-2 --wait
linode-cli ai status
```

Once running, you can call the TEI API:

```bash
curl -X POST http://<host>/embed \
  -H "Content-Type: application/json" \
  -d '{"inputs":["Hello from Linode"]}'
```

Destroy when you're done:

```bash
linode-cli ai destroy --app embeddings-bert --env default
```
