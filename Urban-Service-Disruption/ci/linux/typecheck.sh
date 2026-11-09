#!/usr/bin/env sh

. .venv/bin/activate
python -m mypy ./src/{{cookiecutter.python_import_name}} ./unit_test/
