@echo off
title RecruitAI - All Services (Redis + Celery + Flask)

echo ================================================
echo Starting Redis, Celery (SOLO), and Flask
echo ================================================

:: === Activate venv ===
call venv_enterprise\Scripts\activate.bat || (
    echo Failed to activate venv
    pause
    exit /b 1
)

:: === Start Redis ===
start "Redis Server" cmd /c "C:\Redis\redis-server.exe --maxmemory 256mb --maxmemory-policy allkeys-lru"
timeout /t 3 >nul

:: === Start Celery (SOLO pool – Windows safe) ===
start "Celery Worker" cmd /c ^
"python -m celery -A enterprise_app.celery worker -P solo --loglevel=info"

timeout /t 3 >nul

:: === Start Flask ===
python run.py

pause
