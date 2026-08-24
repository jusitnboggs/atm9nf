@echo off
REM =========================================================================
REM  SELF-RELAUNCH GUARD -- keeps the window open no matter how this script
REM  dies. A cmd PARSE error (bad syntax inside a parenthesised block) aborts
REM  before any code runs, so the :END_PAUSE / pause at the bottom can never
REM  fire and a double-clicked window just vanishes. Running the real work in
REM  a CALLed child means the parent keeps the window open and prints the exit
REM  code even when the child aborts. Set SYNC_NOGUARD=1 to skip this.
REM =========================================================================
if defined SYNC_GUARDED goto :GUARD_DONE
if defined SYNC_NOGUARD goto :GUARD_DONE
set SYNC_GUARDED=1
call "%~f0" %*
echo.
echo [EXIT CODE] %errorlevel%
echo.
echo If the window closed instantly or you see a syntax error above, re-run as:
echo     sync_pack.bat --debug
echo ...which echoes every command and writes sync_debug.log.
echo.
pause
exit /b
:GUARD_DONE

setlocal enabledelayedexpansion
title Modpack Sync Tool
REM %~dp0 ends in a backslash, which escapes the closing quote and breaks
REM parsing ("The syntax of the command is incorrect") on paths containing
REM characters like ( ). The trailing dot keeps the quoting intact.
cd /d "%~dp0."

REM --- Debug mode: run "sync_pack.bat --debug" (or set SYNC_DEBUG=1) to echo
REM     every command as it executes and write a full transcript to
REM     sync_debug.log. The LAST line printed before an error is the culprit.
set "SYNC_LOG=%~dp0sync_debug.log"
if /i "%~1"=="--debug" set "SYNC_DEBUG=1"
if /i "%~1"=="-d" set "SYNC_DEBUG=1"
if defined SYNC_DEBUG (
    echo [DEBUG] Command tracing ON. Transcript: "!SYNC_LOG!"
    echo === sync_pack debug run %DATE% %TIME% === > "!SYNC_LOG!"
    echo [DEBUG] cwd: %CD% >> "!SYNC_LOG!"
    echo on
)

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

if not exist ".git" (
    if defined REPO_URL (
        echo [GIT] Initializing repository from scripts\pack_sync.conf ...
        git init 2>&1
        git remote add origin "!REPO_URL!" 2>&1
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
    echo [CONFIG SYNC] All pack configuration files are already up to date.
    echo.
    goto RUN_MODS
)

echo.
echo [CONFIG SYNC] Updating !CONFIG_COUNT! pack configuration files...
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
if defined SYNC_DEBUG (
    @echo off
    echo.
    echo [DEBUG] Reached END_PAUSE normally ^(no parse error^).
    echo [DEBUG] Transcript written to: !SYNC_LOG!
    echo [DEBUG] Reached END_PAUSE. >> "!SYNC_LOG!"
)
echo.
pause
