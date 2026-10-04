@echo off
rem Isolated V1.4 synthetic QA only; no provider reads or saved preferences.
if not exist "%~dp0petoken.exe" (
    echo Place this launcher beside the development petoken.exe.
    pause
    exit /b 1
)
start "" "%~dp0petoken.exe" --preview-v1-4 --count 3 --language zh_CN
