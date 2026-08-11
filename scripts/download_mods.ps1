# Automated Mod Downloader & Sync Script for ATM9 No Frills
# Downloads added/updated mod jars from Modrinth/CurseForge/CDN links

$ErrorActionPreference = "Continue"
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$instanceRoot = Split-Path -Parent $scriptDir

if (-not (Test-Path "$instanceRoot\mods")) {
    $instanceRoot = Get-Location
}

$modsDir = Join-Path $instanceRoot "mods"
$docsDir = Join-Path $instanceRoot "docs"
$urlsFile = Join-Path $docsDir "mod_downloads.json"
$updatedFile = Join-Path $docsDir "updated_mods.txt"

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "  ATM9 No Frills Mod Sync & Downloader" -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

if (-not (Test-Path $urlsFile)) {
    Write-Host "Error: $urlsFile not found!" -ForegroundColor Red
    exit 1
}

$modUrls = Get-Content $urlsFile -Raw | ConvertFrom-Json

# 1. Clean up explicitly replaced old mod versions (exact matching only, no wildcards)
if (Test-Path $updatedFile) {
    Write-Host "Checking for explicitly replaced old mod versions..." -ForegroundColor Cyan
    $lines = Get-Content $updatedFile | Where-Object { $_ -and -not $_.StartsWith("#") }
    foreach ($line in $lines) {
        if ($line -match "^\s*([^\s]+)\s*->\s*([^\s]+)\s*$") {
            $oldJar = $matches[1]
            $newJar = $matches[2]
            $oldPath = Join-Path $modsDir $oldJar
            if (Test-Path $oldPath) {
                Write-Host "[REMOVING OUTDATED MOD] $oldJar -> Replacing with $newJar" -ForegroundColor Yellow
                Remove-Item $oldPath -Force -ErrorAction SilentlyContinue
            }
        }
    }
}

# 2. Download missing mods
$downloaded = 0
$skipped = 0
$failed = 0
$needsManual = 0
$manualList = @()

foreach ($prop in $modUrls.PSObject.Properties) {
    $filename = $prop.Name
    $url = $prop.Value
    $targetPath = Join-Path $modsDir $filename

    if ($url -eq "LOCAL_CUSTOM") {
        Write-Host "[SKIP] Custom mod (shipped in repo via git): $filename" -ForegroundColor Gray
        $skipped++
        continue
    }

    if ($url -eq "SEARCH_CURSEFORGE" -or [string]::IsNullOrWhiteSpace($url)) {
        if (-not (Test-Path $targetPath)) {
            Write-Host "[MANUAL DOWNLOAD NEEDED] Not shipped in repo, no verified direct URL: $filename" -ForegroundColor Yellow
            $needsManual++
            $manualList += $filename
        } else {
            Write-Host "[OK] Already installed: $filename" -ForegroundColor Green
            $skipped++
        }
        continue
    }

    if (Test-Path $targetPath) {
        Write-Host "[OK] Already installed: $filename" -ForegroundColor Green
        $skipped++
        continue
    }
    
    Write-Host "[DOWNLOADING] $filename ..." -ForegroundColor Yellow
    try {
        Invoke-WebRequest -Uri $url -OutFile $targetPath -UserAgent "Mozilla/5.0"
        Write-Host "  -> Downloaded successfully!" -ForegroundColor Green
        $downloaded++
    } catch {
        Write-Host "  -> Download failed: $_" -ForegroundColor Red
        $failed++
    }
}

Write-Host "`n==========================================================" -ForegroundColor Cyan
Write-Host "  Sync Complete: $downloaded downloaded, $skipped present, $failed failed, $needsManual need manual download" -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

if ($needsManual -gt 0) {
    Write-Host "`nThe following mods are NOT in the repo and have no verified direct download URL." -ForegroundColor Yellow
    Write-Host "Get them manually from CurseForge and place them in mods\:" -ForegroundColor Yellow
    foreach ($m in $manualList) {
        Write-Host "  - $m" -ForegroundColor Yellow
    }
}

if ($failed -gt 0) {
    exit 1
} else {
    exit 0
}
