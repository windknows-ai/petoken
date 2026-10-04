@echo off
rem Packaged synthetic QA only; no provider reads or saved user preferences.
if not exist "%~dp0petoken.exe" (
    echo Place this launcher beside the development petoken.exe.
    pause
    exit /b 1
)
start "" "%~dp0petoken.exe" --preview-v1-3 --count 3 --language en
