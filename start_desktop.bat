@echo off
rem ===========================================================================
rem  MiniCPM-OCR OCR Workbench - Desktop Launcher
rem
rem  Double-click this file: it cleans leftovers, starts the local services,
rem  and opens the workbench in a native desktop window. Closing the window
rem  stops the services this run started.
rem
rem  On first run it prepares the desktop shell dependencies (pywebview via
rem  the Aliyun pypi mirror), which may take a few minutes.
rem
rem  NOTE: this file is intentionally pure ASCII. cmd.exe reads UTF-8 batch
rem  files unreliably and can mangle multi-byte text. The Chinese status
rem  messages come from desktop_app.py, which prints UTF-8 properly.
rem ===========================================================================

setlocal
set "OCR_ROOT=E:\OCR"
set "DESKTOP_PY=%OCR_ROOT%\.desktop\Scripts\python.exe"
set "BASE_PY=C:\Users\lf1\AppData\Local\Microsoft\WindowsApps\PythonSoftwareFoundation.Python.3.13_qbz5n2kfra8p0\python.exe"
set "PIP_INDEX=https://mirrors.aliyun.com/pypi/simple/"
set "FRONTEND_DIST=%OCR_ROOT%\sources\MiniCPM-OCR-main\webdemo\frontend\dist\index.html"

echo.
echo   MiniCPM-OCR OCR Workbench - Desktop
echo   ----------------------------------------
echo.

rem --- 1) desktop shell dependencies ---
if not exist "%DESKTOP_PY%" (
    echo [1/3] First run: preparing the desktop shell environment ...
    if not exist "%BASE_PY%" (
        echo   ERROR: Python 3.13 base not found:
        echo   %BASE_PY%
        echo   Run these two commands manually:
        echo     "%BASE_PY%" -m venv "%OCR_ROOT%\.desktop"
        echo     "%OCR_ROOT%\.desktop\Scripts\python.exe" -m pip install -i %PIP_INDEX% pywebview
        pause
        exit /b 1
    )
    "%BASE_PY%" -m venv "%OCR_ROOT%\.desktop"
    if errorlevel 1 (
        echo   ERROR: failed to create the venv
        pause
        exit /b 1
    )
    "%DESKTOP_PY%" -m pip install --disable-pip-version-check -i %PIP_INDEX% pywebview
    if errorlevel 1 (
        echo   ERROR: failed to install pywebview
        pause
        exit /b 1
    )
    echo   Dependencies ready.
) else (
    echo [1/3] Desktop shell dependencies are ready.
)

rem --- 2) frontend production bundle ---
if not exist "%FRONTEND_DIST%" (
    echo [2/3] No frontend bundle found, building it now - first run is slow ...
    call pwsh -NoProfile -ExecutionPolicy Bypass -File "%OCR_ROOT%\scripts\build-frontend.ps1"
    if errorlevel 1 (
        echo   WARN: frontend build failed.
    )
) else (
    echo [2/3] Frontend bundle is ready.
)

rem --- 3) launch ---
echo [3/3] Starting services and opening the workbench window ...
echo.
"%DESKTOP_PY%" "%OCR_ROOT%\scripts\desktop_app.py"
if errorlevel 1 (
    echo.
    echo The desktop shell exited with an error. See the output above and %OCR_ROOT%\logs
    pause
)
endlocal
