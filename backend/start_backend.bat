@echo off
cd c:\Users\abhin\OneDrive\Desktop\college\ett\ResearchIQ\backend
title Backend_ResearchIQ
call uv run uvicorn main:app --host 0.0.0.0 --port 8000
pause
