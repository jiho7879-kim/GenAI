<#
.SYNOPSIS
    Research Agent — Harness: Run ALL validation checks in one command.

.DESCRIPTION
    Executes the full harness suite:
      1. ruff format check       (formatting)
      2. ruff check              (linting)
      3. Import validation       (all modules load)
      4. pytest                  (unit tests)
    
    Exit code 0 = all passed. Any failure = non-zero exit.

    Usage:
        .\scripts\check_all.ps1
#>

$ErrorActionPreference = "Stop"
$rootDir = Split-Path -Parent (Split-Path -Parent $PSCommandPath)
Set-Location $rootDir

$venvPython = Join-Path $rootDir ".venv\Scripts\python.exe"
if (-not (Test-Path $venvPython)) {
    $venvPython = "python"
}

$passed = 0
$failed = 0

function Run-Step {
    param($Name, $Command)
    Write-Host "`n════════════════════════════════════════════" -ForegroundColor Cyan
    Write-Host "  [$($passed+$failed+1)] $Name" -ForegroundColor Cyan
    Write-Host "════════════════════════════════════════════`n" -ForegroundColor Cyan
    try {
        Invoke-Expression $Command
        if ($LASTEXITCODE -ne 0 -and $LASTEXITCODE -ne $null) { throw "exit code $LASTEXITCODE" }
        Write-Host "  ✅ PASS: $Name" -ForegroundColor Green
        $script:passed++
    } catch {
        Write-Host "  ❌ FAIL: $Name — $_" -ForegroundColor Red
        $script:failed++
    }
}

# ── Step 1: ruff format check ──────────────────────────────
Run-Step -Name "ruff format check" -Command "& `"$venvPython`" -m ruff format --check app.py src/ scripts/ tests/"

# ── Step 2: ruff lint ──────────────────────────────────────
Run-Step -Name "ruff lint" -Command "& `"$venvPython`" -m ruff check app.py src/ scripts/ tests/"

# ── Step 3: Import validation ──────────────────────────────
Run-Step -Name "Import validation" -Command "& `"$venvPython`" scripts/validate_imports.py"

# ── Step 4: pytest ─────────────────────────────────────────
Run-Step -Name "pytest" -Command "& `"$venvPython`" -m pytest tests/ -v --tb=short --no-header 2>&1"

# ── Summary ────────────────────────────────────────────────
Write-Host "`n════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "  RESULTS: $passed passed, $failed failed" -ForegroundColor $(if ($failed -eq 0) {"Green"} else {"Red"})
Write-Host "════════════════════════════════════════════`n" -ForegroundColor Cyan

exit $failed
