@echo off
rem Petoken 2.0 adjustable test build: synthetic data only, nothing real is read or saved.
if not exist "%~dp0petoken.exe" (
    echo Place this launcher beside petoken.exe.
    pause
    exit /b 1
)
start "" "%~dp0petoken.exe" --preview-v2-0 --language zh_CN
