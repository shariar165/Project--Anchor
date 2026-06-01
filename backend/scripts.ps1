# Windows equivalent of Makefile targets
# Usage: .\scripts.ps1 <target>
# Example: .\scripts.ps1 gen-keys

param([string]$target = "help")

$venvPython = "$PSScriptRoot\.venv\Scripts\python.exe"
$venvAlembic = "$PSScriptRoot\.venv\Scripts\alembic.exe"
$venvPytest  = "$PSScriptRoot\.venv\Scripts\pytest.exe"
$venvUvicorn = "$PSScriptRoot\.venv\Scripts\uvicorn.exe"
$venvRuff    = "$PSScriptRoot\.venv\Scripts\ruff.exe"

switch ($target) {
    "gen-keys" {
        & $venvPython -c @"
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PrivateFormat, PublicFormat, NoEncryption
import os
os.makedirs('.keys', exist_ok=True)
pk = Ed25519PrivateKey.generate()
open('.keys/ed25519_private.pem','wb').write(pk.private_bytes(Encoding.PEM, PrivateFormat.PKCS8, NoEncryption()))
open('.keys/ed25519_public.pem','wb').write(pk.public_key().public_bytes(Encoding.PEM, PublicFormat.SubjectPublicKeyInfo))
print('Keys written to .keys/')
"@
    }
    "migrate" {
        & $venvAlembic upgrade head
    }
    "downgrade" {
        & $venvAlembic downgrade -1
    }
    "test" {
        & $venvPytest -x -v
    }
    "dev" {
        Start-Process "docker" -ArgumentList "compose up -d db redis" -NoNewWindow -Wait
        & $venvUvicorn app.main:app --reload --port 8000
    }
    "lint" {
        & $venvRuff check app tests
    }
    default {
        Write-Host "Available targets: gen-keys, migrate, downgrade, test, dev, lint"
        Write-Host "Venv: $PSScriptRoot\.venv"
    }
}
