# ─────────────────────────────────────────────────────────────
# Run the RAG service locally (Option B: RAG on your PC, API on Railway).
#
#   1. Start Ollama first:   ollama serve   (and: ollama pull qwen3:8b)
#   2. Run this script:      .\run-local.ps1
#   3. In a 2nd terminal:    ngrok http 8001
#   4. Copy the ngrok https URL into Railway API var RAG_SERVICE_URL.
#
# First run downloads ~1.5 GB of sentence-transformer models — be patient.
# ─────────────────────────────────────────────────────────────
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

if (-not (Test-Path ".env")) {
    Write-Host "[!] No .env found. Copy .env.example to .env and fill in RAG_INTERNAL_SECRET." -ForegroundColor Yellow
    exit 1
}

# Create venv + install deps on first run.
if (-not (Test-Path ".venv")) {
    Write-Host "[*] Creating virtualenv and installing dependencies (one-time, slow)..." -ForegroundColor Cyan
    python -m venv .venv
    .\.venv\Scripts\python.exe -m pip install --upgrade pip
    .\.venv\Scripts\python.exe -m pip install -r requirements.txt
}

Write-Host "[*] Starting RAG service on http://127.0.0.1:8001 ..." -ForegroundColor Green
Write-Host "    (next: run 'ngrok http 8001' in another terminal)" -ForegroundColor DarkGray
.\.venv\Scripts\uvicorn.exe app.main:app --host 127.0.0.1 --port 8001 --env-file .env
