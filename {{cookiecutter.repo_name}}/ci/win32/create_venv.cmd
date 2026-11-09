rem Short script to initialize virtual environment using venv and pip
rem @echo off

pushd .
cd /D "%~dp0"
py -{{cookiecutter.python_version}} -m venv ..\..\venv
call ..\..\venv\Scripts\activate.bat
python -m pip install pip-tools
popd
