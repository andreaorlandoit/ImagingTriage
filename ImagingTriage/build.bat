@echo off
echo Checking for PyInstaller...
python -c "import PyInstaller" >nul 2>&1
if %errorlevel% neq 0 (
    echo PyInstaller not found. Please install it using: pip install pyinstaller
    pause
    exit /b 1
)

echo Building ImagingTriage.exe...
python -m PyInstaller -i ImagingTriage.ico imaging_triage.py --onefile --noconsole --add-data "lang:lang"
if %errorlevel% neq 0 (
    echo PyInstaller build failed!
    pause
    exit /b 1
)

echo Build complete. The executable should be in the 'dist' folder.
pause