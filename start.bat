@echo off
setlocal
title AI Resume Generator - Start

set "ROOT=%~dp0"
set "BACKEND=%ROOT%backend"
set "FRONTEND=%ROOT%frontend"
set "PY=%BACKEND%\.venv\Scripts\python.exe"

echo ==========================================
echo   AI Resume Generator - One-Click Start
echo ==========================================
echo.

where node >nul 2>nul
if errorlevel 1 (
  echo [ERROR] Node.js not found. Install it from https://nodejs.org
  goto :fail
)

if not exist "%PY%" (
  echo [1/3] First run: creating backend venv and installing dependencies...
  where python >nul 2>nul
  if errorlevel 1 (
    echo [ERROR] Python not found. Install Python 3.10+ first.
    goto :fail
  )
  python -m venv "%BACKEND%\.venv"
  if errorlevel 1 ( echo [ERROR] Failed to create venv & goto :fail )
  "%PY%" -m pip install -q --upgrade pip
  "%PY%" -m pip install -q -r "%BACKEND%\requirements.txt"
  if errorlevel 1 ( echo [ERROR] Failed to install backend dependencies & goto :fail )
) else (
  echo [1/3] Backend venv ready
)

if not exist "%FRONTEND%\node_modules" (
  echo [2/3] First run: installing frontend dependencies...
  pushd "%FRONTEND%"
  call npm install
  if errorlevel 1 ( popd & echo [ERROR] Failed to install frontend dependencies & goto :fail )
  popd
) else (
  echo [2/3] Frontend dependencies ready
)

echo [3/3] Starting services...
echo.

call :port_in_use 8000
if "%PORT_USED%"=="1" (
  echo [SKIP] Port 8000 already in use, backend seems to be running
) else (
  echo [START] Backend  http://127.0.0.1:8000
  start "Resume Backend :8000" cmd /k "cd /d ""%BACKEND%"" && ".venv\Scripts\python.exe" -m uvicorn app.main:app --reload --port 8000"
  call :wait_port 8000 90
  if "%PORT_OK%"=="0" echo [WARN] Backend not ready within 90s, check the backend window
)

call :port_in_use 5173
if "%PORT_USED%"=="1" (
  echo [SKIP] Port 5173 already in use, frontend seems to be running
) else (
  echo [START] Frontend http://localhost:5173
  start "Resume Frontend :5173" cmd /k "cd /d ""%FRONTEND%"" && npm run dev"
  call :wait_port 5173 90
  if "%PORT_OK%"=="0" echo [WARN] Frontend not ready within 90s, check the frontend window
)

echo.
echo Frontend : http://localhost:5173
echo API docs : http://127.0.0.1:8000/docs
echo To stop  : close the two console windows
echo.
start "" http://localhost:5173
ping -n 5 127.0.0.1 >nul
exit /b 0

:port_in_use
set "PORT_USED="
for /f "tokens=*" %%L in ('netstat -ano ^| findstr /r /c:":%~1 .*LISTENING"') do set "PORT_USED=1"
goto :eof

:wait_port
set "PORT_OK=0"
set /a "TRIES=0"
:wait_loop
call :port_in_use %~1
if "%PORT_USED%"=="1" ( set "PORT_OK=1" & goto :eof )
set /a TRIES+=1
if %TRIES% GEQ %~2 goto :eof
ping -n 2 127.0.0.1 >nul
goto :wait_loop

:fail
echo.
echo Startup failed. Fix the problem above, then run this script again.
pause
exit /b 1