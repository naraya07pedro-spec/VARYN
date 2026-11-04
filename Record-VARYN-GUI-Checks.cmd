@echo off
setlocal EnableExtensions DisableDelayedExpansion
cd /d "%~dp0"
if errorlevel 1 (
    echo Could not open the VARYN source folder.
    pause
    exit /b 1
)
echo VARYN OWNER GUI OBSERVATION CHECKLIST
echo Only generated synthetic files. Never use personal folders or login.
echo Open the VARYN desktop in a separate normal-user window.
echo Keep provider on fake and network OFF. Do NOT run as Administrator.
echo Respond yes, no, or skip to each observation after actually testing it.
echo Results are an OWNER SELF-REPORT, not independently verified proof.
echo No report is saved or uploaded by this tool.
where py >nul 2>nul
if not errorlevel 1 (
    py -3 -m varyn.owner_acceptance --synthetic-only --interactive
) else (
    where python >nul 2>nul
    if errorlevel 1 (
        echo Python with Tkinter is required. Nothing was tested.
        pause
        exit /b 1
    )
    python -m varyn.owner_acceptance --synthetic-only --interactive
)
set "result=%errorlevel%"
if not "%result%"=="0" (
    echo INCOMPLETE OR FAILED OWNER CHECKS. Do not enable private-folder access.
) else (
    echo SELF-REPORTED PASS ONLY. Windows GUI verification remains untrusted.
)
pause
exit /b %result%
