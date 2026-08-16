@echo off
chcp 65001 >nul
title Antidetect Tool - Dang chay...

echo.
echo ============================================
echo   ANTIDETECT TOOL - KHOI DONG
echo ============================================
echo.

:: Kiem tra Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [LOI] Chua cai Python! Hay chay setup.bat truoc!
    pause
    exit
)

:: Lay IP de hien thi
for /f "tokens=2 delims=:" %%a in ('ipconfig ^| findstr /R "IPv4"') do (
    set IP=%%a
    goto :found_ip
)
:found_ip
set IP=%IP: =%

echo.
echo [INFO] Tool dang khoi dong...
echo.
echo ============================================
echo   TRUY CAP TOOL TAI:
echo.
echo   May nay    : http://localhost:5333
echo   Dien thoai : http://%IP%:5333
echo   VPS        : http://IP_VPS_CUA_BAN:5333
echo.
echo   Nho mo cong 5333 tren firewall VPS!
echo ============================================
echo.
echo [Nhan Ctrl+C de tat tool]
echo.

python main.py

pause
