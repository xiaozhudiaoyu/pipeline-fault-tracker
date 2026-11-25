@echo off
rem ------------------------------------------------------------
rem  Backend dev launcher: double-click to run.
rem  Equivalent command: .\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
rem  ------------------------------------------------------------
rem  中文注释按 GBK 保存，控制台无论代码页 936 还是 65001，
rem  双语（GBK 字节 / UTF-8 字节）中至少一种可读，避免乱码。
rem ------------------------------------------------------------
setlocal
cd /d "%~dp0"

set "PYTHON=%~dp0.venv\Scripts\python.exe"
if exist "%PYTHON%" goto :run

echo.
echo [ERROR] Virtual env Python not found:
echo   %PYTHON%
echo Please run the following in the backend directory first:
echo   1) uv sync
echo Then re-run this script.
echo.
pause
exit /b 1

:run
echo.
echo Starting API server (uvicorn --reload, bound to 127.0.0.1)...
echo API docs: http://127.0.0.1:8000/docs
echo Stop: press Ctrl+C
echo.
"%PYTHON%" -m uvicorn app.main:app --reload
echo.
echo Server stopped.
pause
endlocal
