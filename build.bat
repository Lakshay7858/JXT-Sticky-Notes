@echo off
REM Builds dist\JXT-Sticky-Notes.exe
setlocal
python -m pip install -r requirements-build.txt || goto :fail
python make_icon.py || goto :fail
python -m PyInstaller --noconfirm --clean --onefile --windowed --noupx ^
  --name "JXT-Sticky-Notes" --icon "icon.ico" main.py || goto :fail
echo.
echo Done! Your exe is in dist\JXT-Sticky-Notes.exe
goto :eof
:fail
echo Build failed.
exit /b 1
