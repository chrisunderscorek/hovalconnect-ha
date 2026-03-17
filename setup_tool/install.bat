@echo off
echo Installiere Hoval Connect Setup Tool...
echo.
pip install playwright requests -q
playwright install chromium --with-deps
echo.
echo Installation abgeschlossen!
pause
