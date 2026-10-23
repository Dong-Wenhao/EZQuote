@echo off
setlocal
cd /d "%~dp0"
python -c "import sys;sys.exit(sys.version_info < (3,10))" >nul 2>&1
if not errorlevel 1 (
  python run.py %*
  goto result
)
py -3 -c "import sys;sys.exit(sys.version_info < (3,10))" >nul 2>&1
if not errorlevel 1 (
  py -3 run.py %*
  goto result
)
echo No usable Python 3.10+ runtime was found.
echo Install Python and enable Add Python to PATH.
echo https://www.python.org/downloads/
pause
exit /b 1
:result
set "launch_exit=%errorlevel%"
if not "%launch_exit%"=="0" (
  echo.
  echo EzQuote could not start. Read the error above.
  echo If port 8765 is in use, close the old service window and start again.
  echo Keep your data and .venv folders.
)
pause
exit /b %launch_exit%
