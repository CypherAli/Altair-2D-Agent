@echo off
cd /d %~dp0
start "" "%LOCALAPPDATA%\Programs\Ollama\ollama.exe" serve
start "Ali" /min pythonw -m agent.ali_app
