@echo off
REM Navigate to the project directory
cd C:\Users\msi\OneDrive\Desktop\idsd\stage2024\Telnet\dev\psr

REM Activate the virtual environment
call venv\Scripts\activate

REM Set Flask app environment variables
set FLASK_APP=app.py
set FLASK_ENV=development  REM Optional: Set environment to development

REM Run Flask
start "" http://127.0.0.1:5000
flask run
