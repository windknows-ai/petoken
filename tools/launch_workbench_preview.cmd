@echo off
rem Disposable V1.4 workbench QA only; no personal database or provider reads.
if not exist "%~dp0petoken.exe" (
    echo Place this launcher beside the isolated development petoken.exe.
    pause
    exit /b 1
)
start "" "%~dp0petoken.exe" --preview-workbench --language zh_CN
