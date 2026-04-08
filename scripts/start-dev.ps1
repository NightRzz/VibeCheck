param(
    [switch]$InstallDeps,
    [switch]$SkipDocker
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

function Resolve-Python {
    $candidates = @(
        (Join-Path $repoRoot ".venv\Scripts\python.exe"),
        (Join-Path $repoRoot "venv\Scripts\python.exe")
    )

    foreach ($candidate in $candidates) {
        if (Test-Path $candidate) {
            return $candidate
        }
    }

    return "python"
}

$python = Resolve-Python

if ($InstallDeps) {
    & $python -m pip install -r requirements.txt
}

if (-not $SkipDocker) {
    docker compose up -d postgres kafka
}

$processes = @(
    @{
        Title = "VibeCheck API"
        Command = "& '$python' -m uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload"
    },
    @{
        Title = "VibeCheck Producer"
        Command = "& '$python' -m uvicorn producer.main:app --host 0.0.0.0 --port 8001 --reload"
    },
    @{
        Title = "VibeCheck Worker"
        Command = "& '$python' -m processor.worker"
    },
    @{
        Title = "VibeCheck YouTube Ingestor"
        Command = "& '$python' -m youtube_ingestor.worker"
    }
)

foreach ($process in $processes) {
    Start-Process powershell `
        -WorkingDirectory $repoRoot `
        -ArgumentList "-NoExit", "-Command", $process.Command `
        -WindowStyle Normal
}

Write-Host "API dashboard: http://localhost:8000"
Write-Host "Producer ingest: http://localhost:8001/ingest"
Write-Host "Worker and YouTube ingestor running in separate PowerShell windows."
