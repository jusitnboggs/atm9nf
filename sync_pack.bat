@echo off
setlocal enabledelayedexpansion
title ATM9 No Frills Pack Sync Tool
cd /d "%~dp0"

color 0B

echo =========================================================================
echo   All The Mods 9 - No Frills (Custom Fork Sync Tool)
echo =========================================================================
echo.

where git >nul 2>nul
if %errorlevel% neq 0 (
    echo [WARNING] Git is not installed or not in PATH.
    echo           Skipping git pack config update. Existing files will be used.
    echo.
) else (
    if not exist ".git" (
        echo [GIT] Initializing repository in instance folder...
        git init >nul 2>nul
        git remote add origin https://github.com/jusitnboggs/atm9nf.git >nul 2>nul
    ) else (
        git remote set-url origin https://github.com/jusitnboggs/atm9nf.git >nul 2>nul
    )

    echo [GIT] Fetching latest pack configs, KubeJS scripts, and tweaks...
    git fetch origin master --quiet 2>nul
    if %errorlevel% equ 0 (
        git reset --hard origin/master >nul 2>nul
        echo [GIT] Pack repository files synced successfully!
    ) else (
        echo [WARNING] Could not connect to GitHub repository.
        echo           Proceeding with local pack files.
    )
    echo.
)

echo [MODS] Running mod sync downloader...
if exist "%~dp0scripts\download_mods.ps1" (
    powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\download_mods.ps1"
    if %errorlevel% equ 0 (
        echo.
        echo [SUCCESS] Mod download and verification complete!
    ) else (
        echo.
        echo [WARNING] Mod downloader finished with errors. Check above log.
    )
) else (
    echo [ERROR] Could not find "%~dp0scripts\download_mods.ps1"!
)

echo.
echo =========================================================================
echo   Sync Complete! You can now launch Minecraft.
echo =========================================================================
echo.
echo Press any key to close this window...
pause >nul
