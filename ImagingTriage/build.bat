@echo off

rem Controlla dove è installato Python per Visual Studio.
set PYTHON_EXE_PATH=
for /f "tokens=*" %%a in ('where python') do if not defined PYTHON_EXE_PATH set "PYTHON_EXE_PATH=%%a"
if not defined PYTHON_EXE_PATH echo [E] Python not found&&goto end
echo [I] Python: %PYTHON_EXE_PATH%

rem Controlla dove si trova la libreria da installare.
set PYTHON_SITE_PACKAGES_PATH=
for /f "tokens=*" %%a in ('pip show pyexiv2 ^| find "Location: "') do set "PYTHON_SITE_PACKAGES_PATH=%%a"
set "PYTHON_SITE_PACKAGES_PATH=%PYTHON_SITE_PACKAGES_PATH:~10, -1%"
echo [I] Library: %PYTHON_SITE_PACKAGES_PATH%

echo Checking for PyInstaller...
%PYTHON_EXE_PATH% -c "import PyInstaller" >nul 2>&1
if %errorlevel% neq 0 (
    echo PyInstaller not found. Please install it using: pip install pyinstaller
    pause
    exit /b 1
)

echo Building ImagingTriage.exe...
%PYTHON_EXE_PATH% -m PyInstaller -i ImagingTriage.ico imaging_triage.py --onefile --noconsole --add-data "lang;lang" --add-data "docs;docs" --paths="%PYTHON_SITE_PACKAGES_PATH%" --hidden-import=pyexiv2
if %errorlevel% neq 0 (
    echo PyInstaller build failed!
    pause
    exit /b 1
)

echo Build complete. The executable should be in the 'dist' folder.

:end
pause