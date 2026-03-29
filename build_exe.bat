@echo off
title MBÇ Kar Yuku V2 EXE Build
echo.
echo MBÇ Mühendislik - Kar Yuku V2 EXE build basliyor...
echo.

python -m PyInstaller ^
  --noconfirm ^
  --clean ^
  --onefile ^
  --windowed ^
  --name mbc_kar_yuku_v2 ^
  --add-data "regions.json;." ^
  --add-data "sk_table.json;." ^
  --add-data "assets;assets" ^
  mbc_kar_yuku_v2.py

echo.
echo Tamamlandi. EXE dosyasi dist klasorundedir.
pause
