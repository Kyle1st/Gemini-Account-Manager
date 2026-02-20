@echo off
chcp 65001 >nul 2>nul
setlocal EnableDelayedExpansion

set APP_NAME=GeminiAccountManager
set ENTRY=main.py

echo.
echo ===================================================
echo   Gemini Account Manager Build Tool
echo ===================================================
echo.

:: Step 1: Ensure PyInstaller is available
echo [1/4] Checking PyInstaller ...
pyinstaller --version >nul 2>&1
if !ERRORLEVEL! neq 0 (
    echo       PyInstaller not found, installing ...
    pip install pyinstaller
)
pyinstaller --version >nul 2>&1
if !ERRORLEVEL! neq 0 (
    echo [ERROR] PyInstaller install failed. Run manually: pip install pyinstaller
    pause
    exit /b 1
)
echo       OK - PyInstaller ready

:: Step 2: Clean previous build
echo [2/4] Cleaning previous build ...
if exist "dist" rmdir /s /q "dist"
if exist "build" rmdir /s /q "build"
if exist "%APP_NAME%.spec" del /f /q "%APP_NAME%.spec"
echo       OK - Clean

:: Step 3: Detect icon
echo [3/4] Checking icon files ...
set ICON_ARG=
set EXTRA_DATA=
if exist "app.ico" (
    set ICON_ARG=--icon=app.ico
    set "EXTRA_DATA=!EXTRA_DATA! --add-data app.ico;."
    echo       Found app.ico
)
if exist "icon.png" (
    set "EXTRA_DATA=!EXTRA_DATA! --add-data icon.png;."
    echo       Found icon.png
)

:: Step 4: Build
echo [4/4] Building ... please wait ...
echo.

pyinstaller ^
    --noconfirm ^
    --clean ^
    --distpath "dist" ^
    --workpath "build" ^
    --name "%APP_NAME%" ^
    --windowed ^
    %ICON_ARG% ^
    --add-data "README.md;." ^
    --add-data "LICENSE;." ^
    %EXTRA_DATA% ^
    --hidden-import "pyotp" ^
    --hidden-import "openpyxl" ^
    --hidden-import "customtkinter" ^
    --hidden-import "DrissionPage" ^
    --exclude-module "matplotlib" ^
    --exclude-module "scipy" ^
    --exclude-module "numpy" ^
    --exclude-module "PIL" ^
    --exclude-module "cv2" ^
    --exclude-module "sklearn" ^
    --exclude-module "torch" ^
    --exclude-module "tensorflow" ^
    --exclude-module "jupyter" ^
    --exclude-module "notebook" ^
    --exclude-module "pytest" ^
    --exclude-module "sphinx" ^
    "%ENTRY%"

if !ERRORLEVEL! neq 0 (
    echo.
    echo [ERROR] Build failed! Check the errors above.
    pause
    exit /b 1
)

echo.
echo ===================================================
echo   BUILD SUCCESS!
echo ===================================================
echo.
echo   Output: dist\%APP_NAME%\%APP_NAME%.exe
echo.
echo   Next steps:
echo     1. Double-click the exe above to test
echo     2. Use Inno Setup with inno_setup.iss to make installer
echo ===================================================
echo.
pause
