@echo off
rem ------------------------------------------------------------
rem  Frontend dev launcher: double-click to run.
rem  If your machine manages Node versions via nvm, add:
rem      nvm use <version>
rem  before "npm run dev".
rem ------------------------------------------------------------
cd /d "%~dp0"
npm run dev
pause
