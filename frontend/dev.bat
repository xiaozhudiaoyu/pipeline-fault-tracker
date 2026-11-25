@echo off
cd /d "%~dp0"
nvm use 16.20.2
npm run dev
pause
