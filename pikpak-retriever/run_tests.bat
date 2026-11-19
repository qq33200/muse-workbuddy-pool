@echo off
chcp 65001 >nul
cd /d %~dp0
python test_pikpak.py --live 蜘蛛侠
echo.
echo 测试报告：%~dp0TEST_REPORT.md
if exist TEST_REPORT.md start "" TEST_REPORT.md
pause
