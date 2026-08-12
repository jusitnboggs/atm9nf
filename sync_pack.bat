@echo off
setlocal enabledelayedexpansion
title ATM9 No Frills Pack Sync Tool
cd /d "%~dp0"

color 0B

echo =========================================================================
echo   All The Mods 9 - No Frills Custom Fork Sync Tool
echo =========================================================================
echo.

if exist ".dev_environment" goto DEV_MODE
if "%ATM9_DEV%"=="1" goto DEV_MODE
goto START_SYNC

:DEV_MODE
echo [DEV MODE] Developer environment detected.
echo           Pack sync and mod downloading are disabled in Dev Mode.
echo           Your local files, configs, and uncommitted code are protected.
echo.
echo =========================================================================
echo   Sync bypassed Dev Mode. You can now launch Minecraft.
echo =========================================================================
echo.
goto END_PAUSE

:START_SYNC
where git >nul 2>nul
if %errorlevel% neq 0 (
    echo [WARNING] Git is not installed or not in PATH.
    echo           Skipping git pack config update. Existing files will be used.
    echo.
    goto RUN_MODS
)

if not exist ".git" (
    echo [GIT] Initializing repository in instance folder...
    git init 2>&1
    git remote add origin https://github.com/jusitnboggs/atm9nf.git 2>&1
) else (
    git remote set-url origin https://github.com/jusitnboggs/atm9nf.git 2>&1
)

echo [GIT] Fetching latest pack configs, KubeJS scripts, and tweaks...
git fetch origin master --quiet 2>&1
if %errorlevel% neq 0 (
    echo [WARNING] Could not connect to GitHub repository.
    echo           Proceeding with local pack files.
    echo.
    goto RUN_MODS
)

set "CONFIG_COUNT=0"
set "SCRIPT_UPDATED=0"
for /f "tokens=*" %%F in ('git diff --name-only HEAD origin/master 2^>nul') do (
    if "!CONFIG_COUNT!"=="0" (
        echo [CONFIG SYNC] Outdated local pack files detected:
    )
    echo   - %%F
    if "%%F"=="sync_pack.bat" set "SCRIPT_UPDATED=1"
    if "%%F"=="scripts/download_mods.ps1" set "SCRIPT_UPDATED=1"
    set /a CONFIG_COUNT+=1
)

if "!CONFIG_COUNT!"=="0" (
    echo [CONFIG SYNC] All pack configuration files are already up to date.
    echo.
    goto RUN_MODS
)

echo.
echo [CONFIG SYNC] Updating !CONFIG_COUNT! pack configuration files...
git reset --hard origin/master 2>&1
echo [CONFIG SYNC] Pack configuration files updated successfully.

if exist "%~dp0mmc-pack.json" (
    copy /y "%~dp0mmc-pack.json" "%~dp0..\mmc-pack.json" >nul 2>nul
    echo [PRISM CONFIG] Synced Prism Launcher Forge version mmc-pack.json.
)

if "!SCRIPT_UPDATED!"=="1" (
    echo.
    echo =========================================================================
    echo   SELF-UPDATE New script version installed. Restarting sync...
    echo =========================================================================
    echo.
    call "%~f0" %*
    goto END_PAUSE
)

:RUN_MODS
echo [MODS] Running mod sync downloader...
if exist "%~dp0scripts\download_mods.ps1" (
    powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\download_mods.ps1" -PromptCleanup -PromptDownload
    if !errorlevel! equ 0 (
        echo.
        echo [SUCCESS] Mod download and verification complete.
    ) else (
        echo.
        echo =========================================================================
        echo   [CRITICAL WARNING] Mod sync finished WITH ERRORS!
        echo   One or more mod files failed to download. Check output above.
        echo =========================================================================
    )
) else (
    echo [ERROR] Could not find "%~dp0scripts\download_mods.ps1".
)

echo.
echo =========================================================================
echo   Sync Complete. You can now launch Minecraft.
echo =========================================================================
echo.

:END_PAUSE
echo Press any key to close this window...
pause
cmd /k
