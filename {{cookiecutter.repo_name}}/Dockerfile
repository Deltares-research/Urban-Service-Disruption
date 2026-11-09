FROM python:{{cookiecutter.python_version}}-bookworm

WORKDIR /app

COPY ./requirements.txt .

RUN pip install -r requirements.txt

COPY . .

ENTRYPOINT ./run.sh