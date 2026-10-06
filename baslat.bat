@echo off
chcp 65001 >nul
cd /d "%~dp0"
if not exist .venv (
  echo Ilk kurulum yapiliyor...
  python -m venv .venv || (echo Python 3.10+ gerekli: https://www.python.org/downloads/ & pause & exit /b 1)
  .venv\Scripts\python -m pip install -r requirements.txt
  .venv\Scripts\python -m playwright install chromium
)
.venv\Scripts\python -c "import pypdf, playwright" 2>nul || (
  echo Eksik paketler kuruluyor...
  .venv\Scripts\python -m pip install -r requirements.txt
  .venv\Scripts\python -m playwright install chromium
)
if not exist data\cvs mkdir data\cvs
if not exist data\profile.json (
  echo.
  echo CV'ni data\cvs klasorune koy (PDF veya DOCX), sonra bu dosyayi tekrar calistir.
  dir /b data\cvs 2>nul | findstr . >nul || (explorer data\cvs & pause & exit /b)
  .venv\Scripts\python run.py setup
)
if not exist data\sessions\linkedin.json (
  echo Acilan tarayicida LinkedIn'e giris yap...
  .venv\Scripts\python run.py login
)
.venv\Scripts\python run.py apply
pause
