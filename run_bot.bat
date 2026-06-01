@echo off
echo ============================================================
echo   TikTok Streak Bot v2.0
echo ============================================================
echo.

:: Check Python
python --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Python is not installed or not in PATH!
    echo Download from: https://www.python.org/downloads/
    pause
    exit /b 1
)

:: Run bot immediately
echo Running streak bot...
echo.
python streak_bot.py --send

echo.
echo ============================================================
echo   Done!
echo ============================================================
pause
