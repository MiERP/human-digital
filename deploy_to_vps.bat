@echo off
chcp 65001 >nul
title One-Click Deploy to VPS 103.20.102.229
cls
echo ==================================================================
echo    🚀 DORAEMON AI DIGITAL HUMAN - ONE-CLICK DEPLOY TO VPS
echo ==================================================================
echo.

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0deploy_to_vps.ps1"

echo.
echo ==================================================================
echo Nhấn phím bất kỳ để đóng cửa sổ này...
pause >nul
