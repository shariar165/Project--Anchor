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
        # OR-Tools' CP-SAT (native) aborts nondeterministically when many solves
        # run in one long-lived, heavily-loaded Python process on Windows (Fatal
        # Python error: Aborted inside cp_model.solve). It is NOT a solver bug —
        # prod sidesteps it with SOLVER_ISOLATION=process (a fresh subprocess per
        # solve). Tests run in thread mode (conftest) for speed + monkeypatching,
        # so we isolate at the FILE level instead: each solver-heavy timetable
        # file gets its own pytest process, then everything else runs in one pass.
        $failed = $false
        Get-ChildItem "$PSScriptRoot\tests\test_timetable*.py" | ForEach-Object {
            Write-Host "== $($_.Name) ==" -ForegroundColor Cyan
            & $venvPytest -q $_.FullName
            if ($LASTEXITCODE -ne 0) { $failed = $true }
        }
        Write-Host "== rest of suite ==" -ForegroundColor Cyan
        & $venvPytest -q --ignore-glob="*test_timetable*.py"
        if ($LASTEXITCODE -ne 0) { $failed = $true }
        if ($failed) { Write-Host "TESTS FAILED" -ForegroundColor Red; exit 1 }
        Write-Host "ALL TESTS PASSED" -ForegroundColor Green
    }
    "test-all-in-one" {
        # The old single-process run. May abort on Windows (see "test" above);
        # kept for CI on Linux / quick single-file runs: .\scripts.ps1 test-all-in-one
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
        Write-Host "Available targets: gen-keys, migrate, downgrade, test, test-all-in-one, dev, lint"
        Write-Host "Venv: $PSScriptRoot\.venv"
    }
}
