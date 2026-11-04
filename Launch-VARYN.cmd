@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if not errorlevel 1 (
    py -3 -m varyn.desktop
    set "exitcode=%errorlevel%"
) else (
    where python >nul 2>nul
    if errorlevel 1 (
        echo Python 3.12 with Tkinter is required. Install Python, then retry.
        exit /b 1
    )
    python -m varyn.desktop
    set "exitcode=%errorlevel%"
)
if not "%exitcode%"=="0" (
    echo VARYN exited with code %exitcode%.
    echo Run: python -m varyn.doctor --json
    pause
)
exit /b %exitcode%
