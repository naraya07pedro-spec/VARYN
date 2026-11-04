@echo off
setlocal EnableExtensions DisableDelayedExpansion
cd /d "%~dp0"
if errorlevel 1 (
    echo Could not open the VARYN folder. Nothing was tested.
    pause
    exit /b 1
)
echo VARYN OFFLINE SYNTHETIC-ONLY SELF-TEST
echo Creates and deletes only two generated temporary example files.
echo No provider sign-in, paid model, user folder selection, or API calls.
echo This is NOT a real GUI-click or private-file safety certification.
where py >nul 2>nul
if not errorlevel 1 (
    py -3 -m varyn.desktop_acceptance --synthetic-only --json
) else (
    where python >nul 2>nul
    if errorlevel 1 (
        echo Python with Tkinter is required. No self-test was run.
        pause
        exit /b 1
    )
    python -m varyn.desktop_acceptance --synthetic-only --json
)
set "result=%errorlevel%"
if not "%result%"=="0" (
    echo FAIL: The synthetic-only safety check did not pass.
    echo Do NOT enable access to personal folders.
) else (
    echo PASS: Synthetic-only CLI self-test. Real GUI acceptance is still pending.
)
pause
exit /b %result%
