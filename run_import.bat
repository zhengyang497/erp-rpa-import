@echo off
chcp 65001 >nul
setlocal EnableExtensions

rem ERP RPA import entry. Default: run all four flows (grouped by module).
rem Usage:
rem   double-click this file
rem   or: run_import.bat
rem   or: run_import.bat option_position
rem   or: run_import.bat all --skip-menu
rem Prerequisite: ERP already logged in and visible.

cd /d "%~dp0"

if exist "%~dp0.venv\Scripts\python.exe" (
  set "PY=%~dp0.venv\Scripts\python.exe"
) else if exist "%~dp0venv\Scripts\python.exe" (
  set "PY=%~dp0venv\Scripts\python.exe"
) else (
  set "PY=python"
)

echo.
echo === erp-rpa-import ===
echo cwd: %CD%
echo Python: %PY%
echo Make sure ERP is logged in. Starting in 5 seconds...
echo.
timeout /t 5 /nobreak >nul

if "%~1"=="" (
  "%PY%" "%~dp0src\run_import.py" all
) else (
  "%PY%" "%~dp0src\run_import.py" %*
)

set "EC=%ERRORLEVEL%"
echo.
if not "%EC%"=="0" (
  echo [done] exit code %EC% - check src\logs\问题报告_*.xlsx and problems_*.log
) else (
  echo [done] ok or empty-skip. report: src\logs\问题报告_日期.xlsx
)

echo Window will close in 3 seconds...
timeout /t 3 /nobreak >nul
exit /b %EC%
