@echo off
REM setup.bat — Windows setup script for Schedule Viewer App
REM Usage: double-click or run in Command Prompt

echo === Schedule Viewer App Setup ===

REM Create virtual environment if it doesn't exist
if not exist "venv" (
    echo Creating Python virtual environment...
    python -m venv venv
)

REM Activate and install dependencies
echo Installing dependencies...
call venv\Scripts\activate.bat
pip install --upgrade pip
pip install -r requirements.txt
pip install pywin32  REM Windows-only: required for VBA macros

echo.
echo === Setup complete ===
echo To run the application:
echo   venv\Scripts\activate
echo   python main.py
echo.
echo On Windows, all features including VBA/CSV-pull will work.
pause