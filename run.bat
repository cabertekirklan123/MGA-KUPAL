@echo off
cd /d "%~dp0"
title EchoHUD Launcher
echo ========================================================
echo Starting EchoHUD Stealth AI Teleprompter...
echo ========================================================
python main.py
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo Application exited with an error.
    pause
)
