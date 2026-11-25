@echo off
rem ------------------------------------------------------------
rem  Todo API һ�������ű���˫�����л���������ִ�о��ɣ�
rem  �ȼ���� .\.venv\Scripts\python.exe -m uvicorn todo_api.main:app --reload
rem  ����Լ�������ļ��� GBK ���棬������ʾ��������У�GBK �ֽ� / UTF-8 �ֽڣ���
rem  ��������̨���۴��� 936 ���� 65001 ����ҳ��������һ���ǿɶ��ġ�
rem ------------------------------------------------------------
setlocal
cd /d "%~dp0"

set "PYTHON=%~dp0.venv\Scripts\python.exe"
if exist "%PYTHON%" goto :run

echo.
echo �����Ҳ������⻷�� Python
echo 错误：找不到虚拟环境 Python
echo %PYTHON%
echo ��������Ŀ��Ŀ¼���� .venv ����װ requirements.txt �е�������
echo 请先在项目根目录创建 .venv 并安装 requirements.txt 中的依赖：
echo   1) python -m venv .venv
echo   2) .venv\Scripts\python.exe -m pip install -r requirements.txt
echo.
pause
exit /b 1

:run
echo.
echo �������� Todo API��uvicorn --reload������������ 127.0.0.1��...
echo 正在启动 Todo API（uvicorn --reload，仅监听本机 127.0.0.1）...
echo �ӿ��ĵ��� http://127.0.0.1:8000/docs
echo 接口文档： http://127.0.0.1:8000/docs
echo ֹͣ���� �� Ctrl+C
echo 停止服务： 按 Ctrl+C
echo.
rem  �Զ����ĵ�ҳ��uvicorn --reload ʵ��Լ 2.4 ��Ű󶨶˿ڣ�
rem  �ʷŵ���̨��ʱԼ 4 ���ٿ��������������������ڷ���������򲻿���
echo �ĵ�ҳ����Լ 4 ����Զ��򿪣�δ�Զ������ֶ����� http://127.0.0.1:8000/docs��
echo 文档页将在约 4 秒后自动打开（未自动打开请手动访问 http://127.0.0.1:8000/docs）
start "" /b cmd /c "ping -n 5 127.0.0.1 >nul & start http://127.0.0.1:8000/docs"
"%PYTHON%" -m uvicorn app.main:app --reload
echo.
echo ������ֹͣ��
echo 服务已停止。
pause
endlocal
