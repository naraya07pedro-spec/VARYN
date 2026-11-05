@echo off
setlocal EnableExtensions DisableDelayedExpansion
cd /d "%~dp0"
if errorlevel 1 (
    echo Could not enter the VARYN folder. Nothing was launched.
    pause
    exit /b 2
)
echo ====================================================
echo VARYN 17S-26 - OFFICIAL APP MANUAL OWNER PILOT
echo ====================================================
echo This will open VARYN and ask fixed yes/no/skip questions.
echo No automatic ChatGPT/Claude/Gemini account sync.
echo Never enter real personal data, passwords, keys or customer files.
echo Run as an ORDINARY user, not Administrator.
echo Use ONLY SYNTHETIC: examples, with VARYN provider fake.
echo The browser opens official websites only with your explicit consent.
where py >nul 2>nul
if not errorlevel 1 (
    py -3 -m varyn.owner_pilot_launcher --manual-only --interactive
) else (
    where python >nul 2>nul
    if errorlevel 1 (
        echo Python 3 with Tkinter not available; pilot NOT started.
        pause
        exit /b 2
    )
    python -m varyn.owner_pilot_launcher --manual-only --interactive
)
set "pilot_result=%errorlevel%"
if not "%pilot_result%"=="0" (
    echo.
    echo Pilot incomplete or failed. This does NOT unlock private-file access.
) else (
    echo.
    echo SELF-REPORTED pilot pass ONLY. This does NOT prove app sync.
)
echo Review the displayed bounded report; no file was uploaded or saved.
pause
exit /b %pilot_result%
