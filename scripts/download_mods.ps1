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

# 1. Clean up outdated versions of updated mods
if (Test-Path $updatedFile) {
    $updatedMods = Get-Content $updatedFile | Where-Object { $_ -and -not $_.StartsWith("#") }
    foreach ($newModName in $updatedMods) {
        $baseName = $newModName -replace '-forge|-mc1\.20\.1|-1\.20\.1|-1\.20|v\d+.*|\d+\.\d+.*',''
        $baseName = $baseName.Trim('-').Trim('_')
        
        if ($baseName) {
            $existing = Get-ChildItem $modsDir -Filter "$baseName*.jar" -ErrorAction SilentlyContinue | Where-Object { $_.Name -ne $newModName }
            foreach ($oldJar in $existing) {
                Write-Host "Removing outdated mod version: $($oldJar.Name)" -ForegroundColor Yellow
                Remove-Item $oldJar.FullName -Force -ErrorAction SilentlyContinue
            }
        }
    }
}

# 2. Download missing mods
$downloaded = 0
$skipped = 0
$failed = 0

foreach ($prop in $modUrls.PSObject.Properties) {
    $filename = $prop.Name
    $url = $prop.Value
    $targetPath = Join-Path $modsDir $filename
    
    if (Test-Path $targetPath) {
        Write-Host "[OK] Already installed: $filename" -ForegroundColor Green
        $skipped++
        continue
    }
    
    if ($url -eq "LOCAL_CUSTOM" -or $url -eq "SEARCH_CURSEFORGE" -or [string]::IsNullOrWhiteSpace($url)) {
        Write-Host "[SKIP] Local/Custom mod (shipped in repo): $filename" -ForegroundColor Gray
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
Write-Host "  Sync Complete: $downloaded downloaded, $skipped present, $failed failed" -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan
