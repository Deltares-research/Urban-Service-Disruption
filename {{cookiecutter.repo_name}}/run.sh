#!/usr/bin/env sh

. .venv/bin/activate
cd src/
python -m {{cookiecutter.python_import_name}}
