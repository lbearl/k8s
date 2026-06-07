# Open WebUI

LLM chat interface at `https://chat.home.bearl.me`.

## Overview

Open WebUI provides a ChatGPT-style web interface connected to:
- **Ollama** on `lukes-macbook-pro.local` (192.168.1.151:11434) — local models (gemma4, qwen3:30b)
- **OpenRouter** — cloud models (Claude, GPT-4, etc.)

## Architecture

```
Browser → ingress-nginx → Open WebUI (port 8080)
                              ├→ Ollama (192.168.1.151:11434)
                              ├→ OpenRouter (openrouter.ai/api/v1)
                              └→ n8n webhooks (for tool/function integration)
```

## Prerequisites

1. **1Password item** `open-webui-secret` in vault `k8s` with fields:
   - `OPENROUTER_API_KEY` — OpenRouter API key
   - `WEBUI_SECRET_KEY` — 64-char hex string (`openssl rand -hex 32`)

2. **Ollama accessible** at `192.168.1.151:11434` with `OLLAMA_HOST=0.0.0.0`

3. **CoreDNS entry** for `chat.home.bearl.me` (already configured)

## First Login

1. Navigate to `https://chat.home.bearl.me`
2. The first account created becomes the admin
3. Signups are disabled after initial setup (`ENABLE_SIGNUP=false`)

## n8n Integration

Open WebUI supports Functions/Tools (Python plugins) that can call external services.
To integrate with n8n:

1. Create an n8n workflow with a Webhook trigger
2. In Open WebUI Admin → Functions, create a tool that calls the n8n webhook URL
3. The LLM can then invoke n8n workflows conversationally

Example use cases:
- "Run the backup workflow"
- "Check the status of my services"
- "Send a notification to Slack"

Internal n8n webhook URL from within the cluster:
```
http://n8n.n8n.svc.cluster.local:5678/webhook/<path>
```

## Configuration

Key environment variables (set in deployment.yaml):

| Variable | Value | Purpose |
|----------|-------|---------|
| `OLLAMA_BASE_URL` | `http://192.168.1.151:11434` | Ollama endpoint |
| `OPENAI_API_BASE_URL` | `https://openrouter.ai/api/v1` | OpenRouter as OpenAI-compatible |
| `OPENAI_API_KEY` | (from 1Password) | OpenRouter API key |
| `WEBUI_SECRET_KEY` | (from 1Password) | Session signing key |
| `ENABLE_SIGNUP` | `false` | Disable public registration |

## Data

All data (users, chats, uploaded documents, RAG collections) persists in the `open-webui-data` PVC mounted at `/app/backend/data`.

## Updating

```bash
kubectl rollout restart deployment/open-webui -n open-webui
```

The image tag is `:main` which pulls latest on restart. Pin to a specific version tag for stability if needed.
