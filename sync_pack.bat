@echo off
title ATM9 No Frills Pack Sync
cd /d "%~dp0"

echo ==========================================================
echo   ATM9 No Frills Pack & Mod Sync
echo ==========================================================
echo.

where git >nul 2>nul
if %errorlevel% equ 0 (
    if not exist ".git" (
        echo [GIT] Initializing repository in current folder...
        git init >nul 2>nul
        git remote add origin https://github.com/jusitnboggs/atm9nf.git >nul 2>nul
    ) else (
        git remote set-url origin https://github.com/jusitnboggs/atm9nf.git >nul 2>nul
    )
    echo [GIT] Fetching and syncing latest pack configs...
    git fetch origin master >nul 2>nul
    git reset --hard origin/master >nul 2>nul
    echo [GIT] Repository files up to date!
    echo.
)

echo [MODS] Running mod sync downloader...
powershell -ExecutionPolicy Bypass -File "%~dp0scripts\download_mods.ps1"

echo.
echo Sync complete! You can now start Minecraft.
pause > nul
