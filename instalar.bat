@echo off
echo ============================================
echo  HAMNA Desktop v1.0 - Instalacion
echo ============================================
echo.
echo [1/3] Creando entorno virtual Python...
python -m venv .venv
if errorlevel 1 ( echo ERROR: Python no encontrado. Instala Python 3.13 && pause && exit )

echo [2/3] Activando entorno...
call .venv\Scripts\activate

echo [3/3] Instalando dependencias...
pip install -r requirements.txt

echo.
echo ============================================
echo  Listo! Para iniciar HAMNA Desktop:
echo     doble clic en iniciar.bat
echo     o ejecuta: python main.py
echo ============================================
pause
