[CmdletBinding()]
param([ValidateRange(1024,65535)][int]$Port = 8765, [switch]$Setup, [switch]$BuildWeb)
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$qa = Join-Path $env:LOCALAPPDATA 'SIRE-Showcase'
$venv = Join-Path $qa 'venv'
$python = Join-Path $venv 'Scripts/python.exe'
New-Item -ItemType Directory -Force -Path $qa | Out-Null
$previousEnv = @{}
foreach ($name in @('SIRE_STATE_DIR','SIRE_WEB_BUILD','OLLAMA_BASE_URL','SIRE_TEXT_MODEL','SIRE_VISION_MODEL')) {
    $previousEnv[$name] = [Environment]::GetEnvironmentVariable($name, 'Process')
}
Push-Location $root
try {
    $env:SIRE_WEB_BUILD = 'dist'
    if ($Setup) {
        if (!(Test-Path $python)) {
            & py -3.11 -m venv $venv
            if ($LASTEXITCODE) { throw 'Python 3.11 with the Windows py launcher is required.' }
        }
        & $python -m pip install -r (Join-Path $root 'requirements-app.lock.txt')
        if ($LASTEXITCODE) { throw 'Application dependency installation failed. Inspect the pip error above.' }
    }
    if (!(Test-Path $python)) { throw 'Run scripts/start_sire.ps1 -Setup first.' }
    & $python -c "import sys; assert sys.version_info[:2] == (3,11), sys.version; import app.api.main"
    if ($LASTEXITCODE) { throw 'Python version or application imports failed. Use the dedicated Python 3.11 environment.' }
    if ($BuildWeb) {
        Push-Location (Join-Path $root 'web')
        try {
            & node -e "const [m,n]=process.versions.node.split('.').map(Number);process.exit((m===20&&n>=19)||(m===22&&n>=12)||m>22?0:1)"
            if ($LASTEXITCODE) { throw 'Use Node 22.12+ or Node 20.19+ for Vite.' }
            & npm.cmd ci
            if ($LASTEXITCODE) { throw 'npm ci failed. Omit -BuildWeb to run the evidence review without Node.' }
            & npm.cmd run build
            if ($LASTEXITCODE) { throw 'TypeScript or Vite build failed. See the build output above.' }
        } finally { Pop-Location }
    }
    if (Get-Command nvidia-smi -ErrorAction SilentlyContinue) {
        & nvidia-smi --query-gpu=name,driver_version,memory.total,memory.free --format=csv
    } else { Write-Warning 'NVIDIA GPU diagnostics unavailable.' }
    $env:OLLAMA_BASE_URL = 'http://127.0.0.1:11434'
    $env:SIRE_TEXT_MODEL = 'qwen3:4b-instruct'
    $env:SIRE_VISION_MODEL = 'qwen3-vl:2b-instruct'
    if (!(Get-Command ollama -ErrorAction SilentlyContinue)) { Write-Warning 'Ollama CLI missing from PATH. Checking the loopback service directly.' }
    try {
        $tags = (Invoke-RestMethod "$env:OLLAMA_BASE_URL/api/tags" -TimeoutSec 4).models
        $expected = (Get-Content 'docs/OLLAMA_MODELS.json' -Raw | ConvertFrom-Json).models
        foreach ($name in @($env:SIRE_TEXT_MODEL, $env:SIRE_VISION_MODEL)) {
            $installed = @($tags | Where-Object name -eq $name)
            $reference = @($expected | Where-Object name -eq $name)
            if ($installed.Count -ne 1 -or $reference.Count -ne 1 -or $installed[0].digest -ne $reference[0].digest) {
                Write-Warning "Unverified model identity for $name. Use deterministic review only until you verify the local tag."
            } else { Write-Host "$name SHA-256 $($installed[0].digest)" }
        }
    } catch { Write-Warning "Ollama tags unavailable. Offline evidence review remains available. $($_.Exception.Message)" }
    $run = Join-Path $qa ([guid]::NewGuid().ToString())
    New-Item -ItemType Directory -Path $run | Out-Null
    $env:SIRE_STATE_DIR = Join-Path $run 'state'
    $allowed = [Net.Sockets.TcpListener]::new([Net.IPAddress]::Loopback,$Port)
    try { $allowed.Start() } catch { throw "Port $Port unavailable. Choose a different -Port." } finally { $allowed.Stop() }
    $server = Start-Process -PassThru -FilePath $python -ArgumentList @('-m','uvicorn','app.api.main:app','--host','127.0.0.1','--port',"$Port") -WorkingDirectory $root -RedirectStandardOutput (Join-Path $run 'stdout.log') -RedirectStandardError (Join-Path $run 'stderr.log')
    try {
        $url = "http://127.0.0.1:$Port"
        $healthy = $false
        for ($i = 0; $i -lt 120; $i++) {
            if ($server.HasExited) { throw "Backend exited ($($server.ExitCode)). See $run/stderr.log" }
            try { $health = Invoke-RestMethod "$url/api/v1/health" -TimeoutSec 4; $healthy = $health.status -eq 'ok' } catch { }
            if ($healthy) { break }
            Start-Sleep -Milliseconds 500
        }
        if (!$healthy) { throw "Backend health timed out. See $run/stderr.log" }
        Write-Host "Evidence review: $url/showcase"
        if (Test-Path 'web/dist/index.html') { Write-Host "Chat and voice workspace: $url/chat" }
        Write-Host "Session files: $run. Press Ctrl+C here to stop."
        while (!$server.HasExited) { Start-Sleep -Seconds 1 }
        if ($server.ExitCode) { throw "Backend exited ($($server.ExitCode)). See $run/stderr.log" }
    } finally { if (!$server.HasExited) { $server.Kill(); $server.WaitForExit() }; $server.Dispose() }
} finally {
    foreach ($name in $previousEnv.Keys) {
        [Environment]::SetEnvironmentVariable($name, $previousEnv[$name], 'Process')
    }
    Pop-Location
}
