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
Write-Host "Checking for outdated versions of updated mods..." -ForegroundColor Cyan

$modTargets = @()
if (Test-Path $urlsFile) {
    $modUrlsObj = Get-Content $urlsFile -Raw | ConvertFrom-Json
    foreach ($prop in $modUrlsObj.PSObject.Properties) {
        $modTargets += $prop.Name
    }
}
if (Test-Path $updatedFile) {
    $updatedMods = Get-Content $updatedFile | Where-Object { $_ -and -not $_.StartsWith("#") }
    $modTargets += $updatedMods
}

$modTargets = $modTargets | Select-Object -Unique

foreach ($newModName in $modTargets) {
    # Extract exact mod base prefix before version string or forge marker
    $baseName = $newModName -replace '[-_](?:forge|mc)?\d+.*|\d+\.\d+.*|\.jar$',''
    $baseName = $baseName.Trim('-').Trim('_')
    
    if ($baseName -and $baseName.Length -ge 3) {
        $existing = @()
        $existing += Get-ChildItem $modsDir -Filter "$baseName-*.jar" -ErrorAction SilentlyContinue | Where-Object { $_.Name -ne $newModName }
        $existing += Get-ChildItem $modsDir -Filter "$baseName_*.jar" -ErrorAction SilentlyContinue | Where-Object { $_.Name -ne $newModName }
        $existing = $existing | Select-Object -Unique
        
        foreach ($oldJar in $existing) {
            Write-Host "[REMOVING OUTDATED MOD] $($oldJar.Name) -> Replacing with $newModName" -ForegroundColor Yellow
            Remove-Item $oldJar.FullName -Force -ErrorAction SilentlyContinue
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
