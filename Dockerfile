FROM python:3.11.6-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    POETRY_VIRTUALENVS_CREATE=false \
    POETRY_NO_INTERACTION=1

COPY pyproject.toml poetry.lock ./
RUN apt update && apt install -y locales && sed -i -e 's/# ru_RU.UTF-8 UTF-8/ru_RU.UTF-8 UTF-8/' /etc/locale.gen && dpkg-reconfigure --frontend=noninteractive locales

ENV LANG=ru_RU.UTF-8 LC_ALL=ru_RU.UTF-8

RUN python -m pip install --upgrade pip setuptools && pip install --no-cache-dir poetry

RUN poetry install --no-root

WORKDIR /app
COPY . /app