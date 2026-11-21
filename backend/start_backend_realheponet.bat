@echo off
set "CONDA_ENV=D:\anaconda3\envs\realheponet"
if not exist "%CONDA_ENV%\python.exe" (
  echo Cannot find Anaconda env: realheponet
  exit /b 1
)
set "PATH=%CONDA_ENV%;%CONDA_ENV%\Library\mingw-w64\bin;%CONDA_ENV%\Library\usr\bin;%CONDA_ENV%\Library\bin;%CONDA_ENV%\Scripts;%CONDA_ENV%\bin;%PATH%"
cd /d "%~dp0"
if not exist logs mkdir logs
"%CONDA_ENV%\python.exe" app.py
