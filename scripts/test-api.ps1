# Test Akili API in isolation (no Docker restart). Run from repo root.
# Usage:
#   .\scripts\test-api.ps1
#   .\scripts\test-api.ps1 -PdfPath .\path\to\file.pdf
#   .\scripts\test-api.ps1 -BaseUrl "http://localhost:8001"   # if your API is on 8001
param(
    [string]$BaseUrl = "",   # empty = try 8000 then 8001
    [string]$PdfPath = ""
)

$ErrorActionPreference = "Stop"

# If no BaseUrl, try 8000 (default docker-compose) then 8001 (127.0.0.1 and localhost)
if (-not $BaseUrl) {
    $ports = 8000, 8001
    $hosts = "127.0.0.1", "localhost"
    foreach ($port in $ports) {
        foreach ($h in $hosts) {
            try {
                $url = "http://${h}:$port/status"
                $null = Invoke-WebRequest -Uri $url -Method Get -TimeoutSec 5 -UseBasicParsing
                $BaseUrl = "http://${h}:$port"
                Write-Host "Using API at $BaseUrl" -ForegroundColor Gray
                break
            } catch { }
        }
        if ($BaseUrl) { break }
    }
    if (-not $BaseUrl) {
        Write-Host "Could not reach API on port 8000 or 8001." -ForegroundColor Red
        Write-Host "  - API is in Docker; backend does NOT connect to another project. Frontend (3001) proxies /api to the api container." -ForegroundColor Gray
        Write-Host "  - Check: docker compose logs api   (is the process running or did it crash?)" -ForegroundColor Yellow
        Write-Host "  - Check: docker compose ps        (are ports 8000/8001 published?)" -ForegroundColor Yellow
        Write-Host "  - Then run: .\scripts\test-api.ps1 -BaseUrl 'http://localhost:8000'" -ForegroundColor Yellow
        exit 1
    }
}

Write-Host "`n=== 1. GET /status (env + DB check) ===" -ForegroundColor Cyan
try {
    $status = Invoke-RestMethod -Uri "$BaseUrl/status" -Method Get
    $status | ConvertTo-Json -Depth 5
    if (-not $status.GOOGLE_API_KEY_set) {
        Write-Host "`n>>> GOOGLE_API_KEY is NOT set. Ingest will return 500. Set it in .env and ensure the API container has env_file: .env" -ForegroundColor Yellow
    } else {
        Write-Host "`n>>> GOOGLE_API_KEY is set." -ForegroundColor Green
    }
} catch {
    Write-Host "FAILED: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host "Is the API running? Try: docker compose up -d api" -ForegroundColor Yellow
    exit 1
}

Write-Host "`n=== 2. GET /documents ===" -ForegroundColor Cyan
try {
    $docs = Invoke-RestMethod -Uri "$BaseUrl/documents" -Method Get
    $docs | ConvertTo-Json -Depth 5
} catch {
    Write-Host "FAILED: $($_.Exception.Message)" -ForegroundColor Red
}

if ($PdfPath -and (Test-Path $PdfPath)) {
    Write-Host "`n=== 3. POST /ingest (file: $PdfPath) ===" -ForegroundColor Cyan
    try {
        $file = Get-Item $PdfPath
        $form = @{ file = $file }
        $ingest = Invoke-RestMethod -Uri "$BaseUrl/ingest" -Method Post -Form $form
        $ingest | ConvertTo-Json
        Write-Host ">>> Ingest OK." -ForegroundColor Green
    } catch {
        $statusCode = $_.Exception.Response.StatusCode.value__
        $reader = New-Object System.IO.StreamReader($_.Exception.Response.GetResponseStream())
        $reader.BaseStream.Position = 0
        $body = $reader.ReadToEnd()
        Write-Host "FAILED ($statusCode): $body" -ForegroundColor Red
        Write-Host ">>> This is the actual error from the API (no restart needed)." -ForegroundColor Yellow
    }
} else {
    Write-Host "`n=== 3. POST /ingest (skipped) ===" -ForegroundColor Cyan
    Write-Host "To test ingest: .\scripts\test-api.ps1 -PdfPath .\path\to\your.pdf" -ForegroundColor Gray
}

Write-Host ""
