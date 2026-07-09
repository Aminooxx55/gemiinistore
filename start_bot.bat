@echo off
title GeminiStoreBot - Running 24/7
color 0A

echo ============================================
echo   GeminiStoreBot - Auto Restart Loop
echo   Close this window to STOP the bot
echo ============================================
echo.

cd /d "C:\Users\AMIN\Downloads\Telegram Desktop\telegram_shop_bot"

:loop
echo [%date% %time%] Starting bot...
python bot.py
echo.
echo [%date% %time%] Bot stopped or crashed. Restarting in 5 seconds...
timeout /t 5 /nobreak
goto loop
