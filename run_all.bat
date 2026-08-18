@echo off
echo ========================================
echo Starting Automated Analysis Pipeline
echo ========================================
echo.

echo Step 1: Running data_dw.py...
python data_dw.py
if %errorlevel% neq 0 (
    echo ERROR: data_dw.py failed with exit code %errorlevel%
    pause
    exit /b %errorlevel%
)
echo data_dw.py completed successfully!
echo.

echo Step 2: Running trend_liner.py...
python trend_liner.py
if %errorlevel% neq 0 (
    echo ERROR: trend_liner.py failed with exit code %errorlevel%
    pause
    exit /b %errorlevel%
)
echo trend_liner.py completed successfully!
echo.

echo Step 3: Running finder.py with verbose and save_plots...
python finder.py -v --save_plots
if %errorlevel% neq 0 (
    echo ERROR: finder.py failed with exit code %errorlevel%
    pause
    exit /b %errorlevel%
)
echo finder.py completed successfully!
echo.

echo ========================================
echo All scripts completed successfully!
echo ========================================
pause