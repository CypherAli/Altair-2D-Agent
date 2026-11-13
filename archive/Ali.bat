@echo off
cd /d %~dp0
"%LOCALAPPDATA%\Programs\Ollama\ollama.exe" serve >nul 2>&1
start "" "%LOCALAPPDATA%\Programs\Ollama\ollama.exe" serve
python -m agent.desktop
pause
