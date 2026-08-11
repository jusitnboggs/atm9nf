@echo off
setlocal enabledelayedexpansion
title ATM9 No Frills Pack Sync Tool
cd /d "%~dp0"

color 0B

echo =========================================================================
echo   All The Mods 9 - No Frills (Custom Fork Sync Tool)
echo =========================================================================
echo.

:: Dev Environment Guard - Do nothing in Dev Environment
if exist ".dev_environment" (
    echo [DEV MODE] Developer environment detected ^(.dev_environment^).
    echo           Pack sync and mod downloading are disabled in Dev Mode.
    echo           Your local files, configs, and uncommitted code are protected.
    echo.
    echo =========================================================================
    echo   Sync bypassed ^(Dev Mode^). You can now launch Minecraft.
    echo =========================================================================
    echo.
    echo Press any key to close this window...
    pause >nul
    exit /b 0
)
if "%ATM9_DEV%"=="1" (
    echo [DEV MODE] Developer environment variable ATM9_DEV detected.
    echo           Pack sync and mod downloading are disabled in Dev Mode.
    echo           Your local files, configs, and uncommitted code are protected.
    echo.
    echo =========================================================================
    echo   Sync bypassed ^(Dev Mode^). You can now launch Minecraft.
    echo =========================================================================
    echo.
    echo Press any key to close this window...
    pause >nul
    exit /b 0
)

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
        :: Check for outdated / updated config files
        set "CONFIG_COUNT=0"
        set "SCRIPT_UPDATED=0"
        for /f "tokens=*" %%F in ('git diff --name-only HEAD origin/master 2^>nul') do (
            if "!CONFIG_COUNT!"=="0" (
                echo [CONFIG SYNC] Outdated local pack files detected:
            )
            echo   - %%F
            if "%%F"=="sync_pack.bat" set "SCRIPT_UPDATED=1"
            set /a CONFIG_COUNT+=1
        )

        if "!CONFIG_COUNT!"=="0" (
            echo [CONFIG SYNC] All pack configuration files are already up to date!
        ) else (
            echo.
            echo [CONFIG SYNC] Updating !CONFIG_COUNT! pack configuration files...
            git reset --hard origin/master >nul 2>nul
            echo [CONFIG SYNC] Pack configuration files updated successfully!
            
            if "!SCRIPT_UPDATED!"=="1" (
                echo.
                echo =========================================================================
                echo   [SELF-UPDATE] New script version installed! Restarting sync...
                echo =========================================================================
                echo.
                call "%~f0" %*
                exit /b 0
            )
        )
    ) else (
        echo [WARNING] Could not connect to GitHub repository.
        echo           Proceeding with local pack files.
    )
    echo.
)

echo [MODS] Running mod sync downloader...
if exist "%~dp0scripts\download_mods.ps1" (
    powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\download_mods.ps1" -PromptCleanup -PromptDownload
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
