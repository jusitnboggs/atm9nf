# Automated Mod Downloader & Sync Script for ATM9 No Frills
# Syncs custom releases from GitHub & verifies mod files in mods/ folder

param (
    [switch]$PromptCleanup,
    [switch]$PromptDownload
)

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

# 1. Clean up explicitly replaced old mod versions
if (Test-Path $updatedFile) {
    $lines = Get-Content $updatedFile | Where-Object { $_ -and -not $_.StartsWith("#") }
    $toRemove = @()
    foreach ($line in $lines) {
        if ($line -match "^\s*([^\s]+)\s*->\s*([^\s]+)\s*$") {
            $oldJar = $matches[1]
            $newJar = $matches[2]
            $oldPath = Join-Path $modsDir $oldJar
            if (Test-Path $oldPath) {
                $toRemove += [PSCustomObject]@{ Old = $oldJar; New = $newJar; Path = $oldPath }
            }
        }
    }

    if ($toRemove.Count -gt 0) {
        Write-Host "`n[OUTDATED MODS FOUND] The following old mod files can be cleaned up:" -ForegroundColor Yellow
        foreach ($item in $toRemove) {
            Write-Host "  - $($item.Old) -> Replace with $($item.New)" -ForegroundColor Yellow
        }

        $doCleanup = $true
        if ($PromptCleanup) {
            $answer = Read-Host "Do you want to run the outdated mod cleanup routine? (Y/N) [default: Y]"
            if ($answer -and $answer.Trim().ToUpper() -eq "N") {
                $doCleanup = $false
            }
        }

        if ($doCleanup) {
            foreach ($item in $toRemove) {
                Write-Host "[REMOVING OUTDATED MOD] $($item.Old) -> Replacing with $($item.New)" -ForegroundColor Yellow
                Remove-Item $item.Path -Force -ErrorAction SilentlyContinue
            }
        } else {
            Write-Host "[SKIPPED] Outdated mod cleanup skipped by user." -ForegroundColor Gray
        }
    } else {
        Write-Host "[CLEANUP] No outdated mod files found in mods/." -ForegroundColor Green
    }
}

# 2. Download missing mods
$modUrls = Get-Content $urlsFile -Raw | ConvertFrom-Json
$missingMods = @()

foreach ($prop in $modUrls.PSObject.Properties) {
    $filename = $prop.Name
    $url = $prop.Value
    $targetPath = Join-Path $modsDir $filename

    if ($url -ne "SEARCH_CURSEFORGE" -and -not [string]::IsNullOrWhiteSpace($url)) {
        if (-not (Test-Path $targetPath)) {
            $missingMods += [PSCustomObject]@{ Name = $filename; Url = $url; Path = $targetPath }
        }
    }
}

$doDownload = $true
if ($missingMods.Count -gt 0) {
    Write-Host "`n[MISSING MODS FOUND] $($missingMods.Count) required mod files need to be downloaded:" -ForegroundColor Yellow
    foreach ($m in $missingMods) {
        Write-Host "  - $($m.Name)" -ForegroundColor Yellow
    }

    if ($PromptDownload) {
        $answer = Read-Host "`nDo you want to download missing/updated mods from the list? (Y/N) [default: Y]"
        if ($answer -and $answer.Trim().ToUpper() -eq "N") {
            $doDownload = $false
        }
    }
}

$downloaded = 0
$skipped = 0
$failed = 0
$needsManual = 0
$manualList = @()

foreach ($prop in $modUrls.PSObject.Properties) {
    $filename = $prop.Name
    $url = $prop.Value
    $targetPath = Join-Path $modsDir $filename

    if ($url -eq "SEARCH_CURSEFORGE" -or [string]::IsNullOrWhiteSpace($url)) {
        if (-not (Test-Path $targetPath)) {
            Write-Host "[PRESENT / CURSEFORGE BASE MOD] Included in launcher base pack: $filename" -ForegroundColor Gray
            $needsManual++
            $manualList += $filename
        } else {
            Write-Host "[OK] Installed: $filename" -ForegroundColor Green
            $skipped++
        }
        continue
    }

    if (Test-Path $targetPath) {
        Write-Host "[OK] Installed: $filename" -ForegroundColor Green
        $skipped++
        continue
    }

    if (-not $doDownload) {
        Write-Host "[SKIPPED] Mod download skipped by user: $filename" -ForegroundColor Gray
        continue
    }
    
    Write-Host "[DOWNLOADING] $filename ..." -ForegroundColor Yellow
    try {
        [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
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

if ($failed -gt 0) {
    exit 1
} else {
    exit 0
}
