@echo off
setlocal enabledelayedexpansion
title Modpack Sync Tool
cd /d "%~dp0"

color 0B

echo =========================================================================
echo   Modpack Sync Tool
echo =========================================================================
echo.

REM --- Developer bypass: presence of .dev_environment (or PACK_DEV=1) skips
REM     all git resets so uncommitted local work is never wiped. ------------
if exist ".dev_environment" goto DEV_MODE
if "%PACK_DEV%"=="1" goto DEV_MODE
if "%ATM9_DEV%"=="1" goto DEV_MODE
goto START_SYNC

:DEV_MODE
echo [DEV MODE] Developer environment detected.
echo           Pack sync and mod downloading are disabled in Dev Mode.
echo           Your local files, configs, and uncommitted code are protected.
echo.
echo =========================================================================
echo   Sync bypassed (Dev Mode). You can now launch Minecraft.
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

REM --- Optional first-time bootstrap config (scripts\pack_sync.conf):
REM       REPO_URL=https://github.com/you/yourpack.git
REM       BRANCH=main
REM     Used only to seed a brand-new clone. An existing repo's own remote and
REM     branch are always auto-detected and take precedence. -----------------
set "REPO_URL="
set "SYNC_BRANCH="
if exist "scripts\pack_sync.conf" (
    for /f "usebackq eol=# tokens=1,* delims==" %%a in ("scripts\pack_sync.conf") do (
        if /i "%%a"=="REPO_URL" set "REPO_URL=%%b"
        if /i "%%a"=="BRANCH" set "SYNC_BRANCH=%%b"
    )
)

REM --- Built-in fallback: a fresh zip / CurseForge install has no .git AND no
REM     scripts\pack_sync.conf, so without this it would never bootstrap the repo
REM     and would keep running the stale bundled scripts (e.g. re-downloading
REM     removed mods). Baking in the pack's own repo lets any install self-init
REM     and pull. An EXISTING clone's own origin/branch still take precedence
REM     (origin is read below; SYNC_BRANCH only forces the release branch). -----
if not defined REPO_URL set "REPO_URL=https://github.com/jusitnboggs/atm9nf.git"
if not defined SYNC_BRANCH set "SYNC_BRANCH=master"

set "FRESH_INIT="
if not exist ".git" (
    if defined REPO_URL (
        echo [GIT] No local repo found. Initializing from !REPO_URL! ...
        git init 2>&1
        git remote add origin "!REPO_URL!" 2>&1
        set "FRESH_INIT=1"
    ) else (
        echo [INFO] No git repository here and no scripts\pack_sync.conf REPO_URL set.
        echo        Skipping config sync; using local pack files.
        echo.
        goto RUN_MODS
    )
)

REM --- Use the repository's EXISTING origin (never overwrite it). ----------
set "ORIGIN_URL="
for /f "delims=" %%u in ('git remote get-url origin 2^>nul') do set "ORIGIN_URL=%%u"
if not defined ORIGIN_URL (
    if defined REPO_URL (
        git remote add origin "!REPO_URL!" 2>&1
        set "ORIGIN_URL=!REPO_URL!"
    ) else (
        echo [INFO] No 'origin' remote configured. Skipping config sync.
        echo.
        goto RUN_MODS
    )
)
echo [GIT] Origin: !ORIGIN_URL!

REM --- Branch: config override, else current branch. Resolved further below
REM     after fetch if still unknown (detached HEAD / fresh clone). ---------
set "BRANCH="
if defined SYNC_BRANCH (
    set "BRANCH=!SYNC_BRANCH!"
) else (
    for /f "delims=" %%b in ('git rev-parse --abbrev-ref HEAD 2^>nul') do set "BRANCH=%%b"
    if "!BRANCH!"=="HEAD" set "BRANCH="
)

echo [GIT] Fetching latest pack configs, KubeJS scripts, and tweaks...
git fetch origin --quiet 2>&1
if %errorlevel% neq 0 (
    echo [WARNING] Could not connect to the remote repository.
    echo           Proceeding with local pack files.
    echo.
    goto RUN_MODS
)

if not defined BRANCH (
    git show-ref --verify --quiet refs/remotes/origin/main && set "BRANCH=main"
)
if not defined BRANCH (
    git show-ref --verify --quiet refs/remotes/origin/master && set "BRANCH=master"
)
if not defined BRANCH (
    echo [WARNING] Could not determine the remote branch. Skipping config sync.
    echo.
    goto RUN_MODS
)
echo [GIT] Branch: !BRANCH!

set "CONFIG_COUNT=0"
set "SCRIPT_UPDATED=0"
for /f "tokens=*" %%F in ('git diff --name-only HEAD origin/!BRANCH! 2^>nul') do (
    if "!CONFIG_COUNT!"=="0" (
        echo [CONFIG SYNC] Outdated local pack files detected:
    )
    echo   - %%F
    if "%%F"=="sync_pack.bat" set "SCRIPT_UPDATED=1"
    if "%%F"=="scripts/download_mods.ps1" set "SCRIPT_UPDATED=1"
    set /a CONFIG_COUNT+=1
)

if "!CONFIG_COUNT!"=="0" (
    if "!FRESH_INIT!"=="1" (
        REM Fresh git init has an unborn HEAD, so the diff above finds nothing.
        REM Force the checkout so the freshly-initialized install actually gets
        REM origin's files instead of keeping the stale bundled ones.
        echo [CONFIG SYNC] Fresh install -- checking out !BRANCH! from origin...
        set "SCRIPT_UPDATED=1"
    ) else (
        echo [CONFIG SYNC] All pack configuration files are already up to date.
        echo.
        goto RUN_MODS
    )
)

echo.
echo [CONFIG SYNC] Updating pack configuration files...
git reset --hard origin/!BRANCH! 2>&1
echo [CONFIG SYNC] Pack configuration files updated successfully.

if exist "%~dp0mmc-pack.json" (
    copy /y "%~dp0mmc-pack.json" "%~dp0..\mmc-pack.json" >nul 2>nul
    echo [PRISM CONFIG] Synced Prism Launcher loader mmc-pack.json.
)

if "!SCRIPT_UPDATED!"=="1" (
    echo.
    echo =========================================================================
    echo   SELF-UPDATE: New script version installed. Restarting sync...
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
echo.
pause
