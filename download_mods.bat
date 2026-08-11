@echo off
title ATM9 No Frills Mod Sync Downloader
cd /d "%~dp0"
echo ==========================================================
echo   ATM9 No Frills Mod Sync Downloader
echo ==========================================================
echo.
powershell -ExecutionPolicy Bypass -File "%~dp0scripts\download_mods.ps1"
echo.
echo Sync complete. Press any key to exit.
pause > nul
