@echo off
title ATM9 No Frills Git Setup & Sync
cd /d "%~dp0"

echo ==========================================================
echo   ATM9 No Frills Repository Sync
echo   (Supports non-empty Prism Launcher instance directories)
echo ==========================================================
echo.

if not exist ".git" (
    echo [INIT] Initializing Git repository in current folder...
    git init
    git remote add origin https://github.com/jusitnboggs/atm9nf.git
) else (
    echo [CONFIG] Git repository found. Updating remote URL...
    git remote set-url origin https://github.com/jusitnboggs/atm9nf.git
)

echo.
echo [FETCH] Fetching latest pack commits from origin...
git fetch origin master

echo.
echo [SYNC] Syncing custom configs, scripts, and mappers over local directory...
git reset --hard origin/master

echo.
echo ==========================================================
echo   Git files synced successfully!
echo   Running mod sync downloader...
echo ==========================================================
echo.

call download_mods.bat
