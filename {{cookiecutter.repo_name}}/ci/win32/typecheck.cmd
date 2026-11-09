REM script to run mypy type checker on this source tree.
pushd .
cd /D "%~dp0"
cd ..\..\
call .\venv\Scripts\activate
set PYTHONPATH=.\src\{{cookiecutter.python_import_name}};%$PYTHONPATH%
python -m mypy ./src/{{cookiecutter.python_import_name}} ./unit_test/
popd