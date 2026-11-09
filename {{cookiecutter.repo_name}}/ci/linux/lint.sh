#!/usr/bin/env sh

. .venv/bin/activate
flake8 ./src/{{cookiecutter.python_import_name}}
