@echo off
rem Start the local control stub and show CLI usage. Not a GUI.
rem Repo-relative: this file lives in control\desktop\.
setlocal
cd /d "%~dp0"
where python >nul 2>&1
if not errorlevel 1 goto :py
where py >nul 2>&1
if not errorlevel 1 goto :py3
echo Python 3 is required to start the control stub.
echo See control\README.md and control\desktop\WINDOWS.md
exit /b 1

:py
python "%~dp0launch_stub.py" %*
exit /b %ERRORLEVEL%

:py3
py -3 "%~dp0launch_stub.py" %*
exit /b %ERRORLEVEL%
