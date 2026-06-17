# Running the RAG service on your PC, reached by the Railway API via ngrok

**Topology (Option B):** the lightweight Core API + Postgres + Redis stay on
Railway. The heavy AI (sentence-transformer embedder + reranker + Ollama
generator) all run on your own PC. The Railway API proxies `/ai/chat` to your
PC through an ngrok tunnel.

```
Vercel frontends ──> Railway API ──(ngrok https)──> RAG service (your PC) ──> Ollama (your PC)
                         │
                         └──> Postgres + Redis (Railway)
```

**Trade-off:** AI chat only works while your PC + ngrok + Ollama are running.
Everything else on the site works 24/7 regardless. Good for demos you control.

---

## One-time setup on the PC

1. **Install Ollama** and pull the models:
   ```powershell
   ollama pull qwen3:8b
   ollama pull qwen3:1.7b
   ```
2. **Install ngrok** and sign in (free account):
   ```powershell
   ngrok config add-authtoken <your-token>
   ```
   Recommended: claim your **one free static domain** in the ngrok dashboard so
   the URL doesn't change every restart (otherwise you must update Railway each
   time — see step 4).
3. **Configure the RAG env file:**
   ```powershell
   cd services/rag
   copy .env.example .env
   ```
   Edit `.env` and set `RAG_INTERNAL_SECRET` to the **exact same value** you set
   on the Railway API service. Leave `OLLAMA_BASE_URL=http://localhost:11434`
   and `DISABLE_AI_WARMUP=false`.

---

## Every time you want AI working

1. **Start Ollama** (if not already running):
   ```powershell
   ollama serve
   ```
2. **Start the RAG service** (creates the venv + installs deps on first run —
   first run also downloads ~1.5 GB of models, so be patient):
   ```powershell
   cd services/rag
   .\run-local.ps1
   ```
   Wait for `Application startup complete`. On first start it also ingests the
   sample legal corpus into ChromaDB.
3. **Open the tunnel** in a second terminal:
   ```powershell
   ngrok http 8001
   ```
   Copy the `https://....ngrok-free.app` (or your static domain) URL.
4. **Point Railway at it.** On the Railway **API** service → Variables:
   ```
   RAG_SERVICE_URL = https://<your-ngrok-url>     # no trailing slash
   ```
   Save — the API redeploys automatically. (If you claimed a static ngrok
   domain, you only ever set this once.)

---

## Verify it works

```bash
# From anywhere — exercises Railway API -> ngrok -> your PC RAG:
curl https://project-anchor-production-e5ae.up.railway.app/ai/health
```
Expect the embedder/chromadb/ollama fields to report `ok` (not `disabled` /
`unavailable`). If you see `disabled`, `DISABLE_AI_WARMUP` is still true on the
**PC** `.env`. If you get a 503, the tunnel/RAG isn't up or `RAG_SERVICE_URL`
is wrong. If you get 403 from RAG, the `RAG_INTERNAL_SECRET` values don't match.

## Common gotchas

- **`RAG_SERVICE_URL` must include `https://` and have no trailing slash.**
- **Secrets must match** between the PC `.env` and the Railway API var.
- **Start Ollama before RAG** so corpus ingestion (which uses the LLM for
  contextual prefixes) can reach it.
- The free ngrok URL **changes on every restart** unless you use a static
  domain — update `RAG_SERVICE_URL` whenever it changes.
