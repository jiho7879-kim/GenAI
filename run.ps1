# Research Agent — Launch wrapper (PowerShell)
# Automatically starts Ollama, then launches Streamlit.
# Captures Streamlit's stdout/stderr to timestamped log files.
#
# Usage:
#   .\run.ps1              # normal launch
#   .\run.ps1 -OpenBrowser # also opens browser window

param(
    [switch]$OpenBrowser
)

$ProjectRoot = Split-Path -Parent $PSCommandPath
$LogDir = Join-Path $ProjectRoot "logs"
$VenvDir = Join-Path $ProjectRoot ".venv"
$VenvScripts = Join-Path $VenvDir "Scripts"
$VenvPython = Join-Path $VenvScripts "python.exe"

# Ensure logs directory
if (-not (Test-Path $LogDir)) {
    New-Item -ItemType Directory -Path $LogDir -Force | Out-Null
}

# Timestamp for log file names
$Timestamp = Get-Date -Format "yyyy-MM-dd_HHmmss"
$OutFile = Join-Path $LogDir "streamlit_out_$Timestamp.log"
$ErrFile = Join-Path $LogDir "streamlit_err_$Timestamp.log"

Write-Host "=== Research Agent ===" -ForegroundColor Cyan
Write-Host "Project : $ProjectRoot"
Write-Host ""

# ---------------------------------------------------------------
# 1. Find Ollama
# ---------------------------------------------------------------
$OllamaExe = $null
$PossiblePaths = @(
    "ollama.exe",                                          # PATH
    "$env:LOCALAPPDATA\Programs\Ollama\ollama.exe",        # Windows default install
    "$env:USERPROFILE\scoop\shims\ollama.exe",             # Scoop install
    "C:\Program Files\Ollama\ollama.exe"                   # System-wide install
)

foreach ($p in $PossiblePaths) {
    $resolved = Get-Command $p -ErrorAction SilentlyContinue
    if ($resolved) { $OllamaExe = $resolved.Source; break }
}

if (-not $OllamaExe) {
    Write-Host "[WARN] Ollama not found. Install from https://ollama.com" -ForegroundColor Yellow
    Write-Host "       The app will still launch, but LLM features require Ollama." -ForegroundColor Yellow
    Write-Host ""
} else {
    Write-Host "[OK] Ollama found: $OllamaExe" -ForegroundColor Green

    # ---------------------------------------------------------------
    # 2. Start Ollama if not already running
    # ---------------------------------------------------------------
    $ollamaRunning = $false
    try {
        $null = Invoke-WebRequest -Uri "http://localhost:11434/api/tags" -TimeoutSec 3 -UseBasicParsing -ErrorAction Stop
        $ollamaRunning = $true
    } catch {
        $ollamaRunning = $false
    }

    if (-not $ollamaRunning) {
        Write-Host "[...] Starting Ollama server..." -ForegroundColor Yellow
        # Start in background with hidden window
        $ollamaProcess = Start-Process -FilePath $OllamaExe -ArgumentList "serve" -WindowStyle Hidden -PassThru
        Write-Host "[...] Waiting for Ollama to be ready..." -NoNewline

        # Poll until ready (up to 30 seconds)
        $ready = $false
        for ($i = 0; $i -lt 30; $i++) {
            Start-Sleep -Seconds 1
            try {
                $null = Invoke-WebRequest -Uri "http://localhost:11434/api/tags" -TimeoutSec 2 -UseBasicParsing -ErrorAction Stop
                $ready = $true
                Write-Host " ready!" -ForegroundColor Green
                break
            } catch {
                Write-Host "." -NoNewline
            }
        }

        if (-not $ready) {
            Write-Host ""
            Write-Host "[ERROR] Ollama failed to start within 30 seconds." -ForegroundColor Red
            Write-Host "        Try running 'ollama serve' manually in another terminal." -ForegroundColor Yellow
            Write-Host ""
        } else {
            Write-Host "[OK] Ollama server is running" -ForegroundColor Green
        }
    } else {
        Write-Host "[OK] Ollama server already running" -ForegroundColor Green
    }

    # ---------------------------------------------------------------
    # 3. Check required models
    # ---------------------------------------------------------------
    try {
        $tagsResp = Invoke-WebRequest -Uri "http://localhost:11434/api/tags" -TimeoutSec 5 -UseBasicParsing
        $tags = $tagsResp.Content | ConvertFrom-Json
        $availableModels = $tags.models | ForEach-Object { $_.name }
        $requiredModels = @("qwen2.5:1.5b")  # fast non-thinking model for RAG Q&A

        foreach ($model in $requiredModels) {
            if ($model -notin $availableModels) {
                Write-Host "[...] Pulling model $model (first download may take a while)..." -ForegroundColor Yellow
                & $OllamaExe pull $model 2>&1 | Out-Null
                Write-Host "[OK] Model $model ready" -ForegroundColor Green
            } else {
                Write-Host "[OK] Model $model available" -ForegroundColor Green
            }
        }
    } catch {
        Write-Host "[WARN] Could not check available models." -ForegroundColor Yellow
    }
    Write-Host ""
}

# ---------------------------------------------------------------
# 4. Launch Streamlit
# ---------------------------------------------------------------
Write-Host "Log dir : $LogDir"
Write-Host "Out     : $OutFile"
Write-Host "Err     : $ErrFile"
Write-Host ""

if ($OpenBrowser) {
    Start-Process -NoNewWindow -FilePath $VenvPython -ArgumentList "-m", "streamlit", "run", "app.py" `
        -RedirectStandardOutput $OutFile -RedirectStandardError $ErrFile
    Start-Sleep -Seconds 5
    Start-Process "http://localhost:8501"
} else {
    # 2>&1 merges stderr into stdout, but PowerShell converts stderr lines to
    # ErrorRecord objects. Catch them explicitly to avoid red PowerShell errors.
    & $VenvPython -m streamlit run app.py 2>&1 |
        ForEach-Object {
            if ($_ -is [System.Management.Automation.ErrorRecord]) {
                $line = $_.ToString()
                $line | Out-File -FilePath $ErrFile -Append
                # Write to console without triggering PowerShell error display
                Write-Host $line -ForegroundColor DarkYellow
            } else {
                $_ | Out-File -FilePath $OutFile -Append
                $_ | Out-File -FilePath $ErrFile -Append
                $_
            }
        }
}
