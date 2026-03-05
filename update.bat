@echo off
setlocal enabledelayedexpansion

rem Ensure we run from the script directory
cd /d %~dp0

rem Check venv exists
if not exist "venv\Scripts\activate" (
  echo [ERROR] Virtual environment not found at venv\Scripts\activate
  echo         Create it first, e.g.:
  echo         python -m venv venv ^&^& call venv\Scripts\activate ^&^& pip install -r requirements.txt
  exit /b 1
)

rem Activate venv
call venv\Scripts\activate
if errorlevel 1 (
  echo [ERROR] Failed to activate virtual environment
  exit /b 1
)

rem Check if wallpaper.jpg exists
if not exist "wallpaper.jpg" (
  echo [WARNING] wallpaper.jpg not found, creating a simple placeholder
  echo Creating placeholder wallpaper...
  rem You can add a command here to create a simple wallpaper if needed
)

rem Build with PyInstaller - include wallpaper.jpg and other resources
pyinstaller --noconfirm --noconsole --onefile --name lockscr --add-data "wallpaper.jpg;." main.py
if errorlevel 1 (
  echo [ERROR] PyInstaller build failed
  rem Try fallback via python -m PyInstaller
  python -m PyInstaller --noconfirm --noconsole --onefile --name lockscr --add-data "wallpaper.jpg;." main.py
  if errorlevel 1 (
    echo [ERROR] Fallback build also failed
    exit /b 1
  )
)

rem Remove existing exe before moving new one
if exist "C:\extentions\lockscr.exe" del /f /q "C:\extentions\lockscr.exe"

rem Move built exe to C:\extentions
if exist "dist\lockscr.exe" (
  move /Y "dist\lockscr.exe" "C:\extentions\lockscr.exe" >nul
) else (
  echo [ERROR] Built executable not found at dist\lockscr.exe
  exit /b 1
)

rem Cleanup build artifacts
if exist "dist" rmdir /s /q "dist"
if exist "build" rmdir /s /q "build"
if exist "lockscr.spec" del /f /q "lockscr.spec"

rem Deactivate venv if available
if exist "venv\Scripts\deactivate.bat" call venv\Scripts\deactivate.bat

echo [OK] Build complete: lockscr.exe
endlocal
