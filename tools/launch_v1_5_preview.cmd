@echo off
rem Isolated V1.5 synthetic QA only: Codex (blue) and Claude Code (gold) stars.
rem No provider reads or saved preferences.
if not exist "%~dp0petoken.exe" (
    echo Place this launcher beside the development petoken.exe.
    pause
    exit /b 1
)
start "" "%~dp0petoken.exe" --preview-v1-5 --provider mixed --count 4 --language zh_CN
