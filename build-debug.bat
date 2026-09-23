@echo off
REM Console build to SEE errors
setlocal
python -m pip install -r requirements-build.txt || goto :fail
python make_icon.py || goto :fail
python -m PyInstaller --noconfirm --clean --onefile --console ^
  --name "JXT-Sticky-Notes-debug" --icon "icon.ico" main.py || goto :fail
echo.
echo Done! Your exe is in dist\JXT-Sticky-Notes-debug.exe
goto :eof
:fail
echo Build failed.
exit /b 1
