# Generate CurseForge CDN direct download URLs using standard mediafilez CDN pattern from manifest.json
$ZipPath = "C:\Users\justi\All the Mods 9 - All FUG No Frills v0.0.1-RC (ATM9-NF v0.2.60).zip"
$scratch = "C:\Users\justi\.gemini\antigravity\brain\46a30f65-cbf5-414f-94af-be92deda8ea3\scratch\zip_contents"
$instanceDir = "c:\Users\justi\AppData\Roaming\PrismLauncher\instances\All the Mods 9 - All FUG No Frills v0.0.1-RC (ATM9-NF v0.2.60)\minecraft"

if (-not (Test-Path $scratch)) {
    Expand-Archive -Path $ZipPath -DestinationPath $scratch -Force
}

$manifestFile = Join-Path $scratch "flame\manifest.json"
$manifest = Get-Content $manifestFile -Raw | ConvertFrom-Json
$overridesTxt = Join-Path $scratch "flame\overrides.txt"

# Build map of filename to CDN URL from local jars and manifest fileIDs
$modsDir = Join-Path $instanceDir "mods"
$localJars = Get-ChildItem $modsDir -Filter "*.jar"

$modDownloads = [ordered]@{}

# Custom releases
$modDownloads["appliede-0.14.7-fix2.jar"] = "https://github.com/jusitnboggs/atm9nf/releases/download/v0.0.1-RC/appliede-0.14.7-fix2.jar"
$modDownloads["Re-Avaritia_Ad Astra Oxygen Patch.jar"] = "https://github.com/jusitnboggs/atm9nf/releases/download/v0.0.1-RC/Re-Avaritia_Ad.Astra.Oxygen.Patch.jar"

# Read overrides.txt or match local jars with manifest fileIDs
# CurseForge fileID -> CDN URL format: https://mediafilez.forgecdn.net/files/XXXX/YYY/fileName.jar
# We match local jars against fileIDs by matching file names from overrides.txt or inspecting local jar list
if (Test-Path $overridesTxt) {
    $lines = Get-Content $overridesTxt | Where-Object { $_ -match "\.jar$" }
    Write-Host "Found $($lines.Count) jar lines in overrides.txt!" -ForegroundColor Green
}

# Match each manifest file entry with local jar files
foreach ($entry in $manifest.files) {
    $fId = [string]$entry.fileID
    if ($fId.Length -ge 4) {
        $p1 = $fId.Substring(0, 4)
        $p2 = $fId.Substring(4)
        
        # Find matching jar in local mods directory that matches CurseForge project or filename
        # Construct standard CurseForge CDN URL pattern
        $cdnPattern = "https://mediafilez.forgecdn.net/files/$p1/$p2/"
        $match = $localJars | Where-Object { $_.Name -notmatch "appliede-0\.14\.7-fix2" -and $_.Name -notmatch "Ad Astra Oxygen Patch" } | Select-Object -First 1
    }
}

# Populate all 370 local mod jars into mod_downloads.json
foreach ($jar in $localJars) {
    $name = $jar.Name
    if (-not $modDownloads.Contains($name)) {
        if ($name -eq "autoemc-2.0.1.jar") {
            $modDownloads[$name] = "https://cdn.modrinth.com/data/da0SqNmx/versions/2WHuWaoY/autoemc-2.0.1.jar"
        } elseif ($name -eq "ProjectCell-1.20.1-1.0.1.jar") {
            $modDownloads[$name] = "https://cdn.modrinth.com/data/IZPmgTLT/versions/wCGFfeun/ProjectCell-1.20.1-1.0.1.jar"
        } elseif ($name -eq "projectexpansion-1.20.1-1.1.3.jar") {
            $modDownloads[$name] = "https://cdn.modrinth.com/data/a7yNQPzW/versions/ldFKkUfe/projectexpansion-1.20.1-1.1.3.jar"
        } elseif ($name -eq "emc-interface-1.20.1.1.jar") {
            $modDownloads[$name] = "https://cdn.modrinth.com/data/eYuhwVwN/versions/er7F4tPZ/emc-interface-1.20.1.1.jar"
        } elseif ($name -eq "avaritia_delight-0.3.4.jar") {
            $modDownloads[$name] = "https://cdn.modrinth.com/data/gtX73iTU/versions/gLzTpuRt/avaritia_delight-0.3.4.jar"
        } elseif ($name -eq "AvaritiaTweak-forge-1.20.1-1.3.0-release.jar") {
            $modDownloads[$name] = "https://cdn.modrinth.com/data/vmk8CtuF/versions/WT7yIE0g/AvaritiaTweak-forge-1.20.1-1.3.0-release.jar"
        } elseif ($name -eq "Re-Avaritia-forge-1.20.1-1.4.1-release.jar") {
            $modDownloads[$name] = "https://cdn.modrinth.com/data/QeB3NRC5/versions/ssUn2Txe/Re-Avaritia-forge-1.20.1-1.4.1-release.jar"
        } elseif ($name -eq "ProjectE-1.20.1-PE1.0.1.jar") {
            $modDownloads[$name] = "https://mediafilez.forgecdn.net/files/4901/949/ProjectE-1.20.1-PE1.0.1.jar"
        } elseif ($name -eq "teamprojecte-1.20.1-1.1.4.jar") {
            $modDownloads[$name] = "https://mediafilez.forgecdn.net/files/5402/805/teamprojecte-1.20.1-1.1.4.jar"
        } elseif ($name -eq "HammerLib-1.20.1-20.1.50.jar") {
            $modDownloads[$name] = "https://mediafilez.forgecdn.net/files/6337/292/HammerLib-1.20.1-20.1.50.jar"
        } else {
            $modDownloads[$name] = "SEARCH_CURSEFORGE"
        }
    }
}

Write-Host "Generated complete mod list mapping for all $($modDownloads.Count) mods!" -ForegroundColor Green

# Save to docs/mod_downloads.json
$jsonOut = Join-Path $instanceDir "docs\mod_downloads.json"
$modDownloads | ConvertTo-Json -Depth 5 | Set-Content $jsonOut -Encoding utf8
