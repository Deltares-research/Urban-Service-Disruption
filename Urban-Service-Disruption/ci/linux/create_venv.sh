#!/usr/bin/env sh

python{{cookiecutter.python_version}} -m venv ./.venv
. .venv/bin/activate
pip3 install pip-tools
