@echo off
setlocal
cd /d "%~dp0"
set HF_HUB_ENABLE_HF_TRANSFER=0
set HF_HUB_DISABLE_XET=1
set "PYEXE="
for /f "delims=" %%P in ('py -3.12 -c "import sys; print(sys.executable)" 2^>nul') do set "PYEXE=%%P"
if not defined PYEXE (
    for /f "delims=" %%P in ('uv python find 3.12 2^>nul') do set "PYEXE=%%P"
)
if not defined PYEXE (
    echo Python 3.12 is required. Install it from python.org, then run this again.
    exit /b 1
)
if not exist ".venv\Scripts\python.exe" (
    "%PYEXE%" -m venv .venv
    if errorlevel 1 (
        echo Could not create the virtual environment with Python 3.12.
        exit /b 1
    )
)
call ".venv\Scripts\activate.bat"
if not exist ".venv\.deps-installed" (
    python -m pip install --upgrade pip
    python -m pip install -r requirements.txt
    if errorlevel 1 exit /b 1
    echo ok> ".venv\.deps-installed"
)
python -m stele.app
