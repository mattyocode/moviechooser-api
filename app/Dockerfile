FROM python:3.9.5-slim-buster

WORKDIR /app

# set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1
ENV PIP_NO_CACHE_DIR off
ENV PIP_DISABLE_PIP_VERSION_CHECK on
ENV PIP_DEFAULT_TIMEOUT=100
ENV POETRY_VERSION 1.0.0
ARG SECRET_KEY=runtimetempsecretkey

# install system deps
RUN apt-get update \
  && apt-get -y install netcat gcc postgresql \
  && apt-get clean

RUN pip install "poetry==$POETRY_VERSION"

COPY poetry.lock pyproject.toml /app/

RUN poetry config virtualenvs.create false \
  && poetry install --no-interaction --no-ansi

# copy entrypoint.sh
COPY ./entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

COPY . .

# run entrypoint.sh
ENTRYPOINT ["/app/entrypoint.sh"]

CMD gunicorn config.wsgi:application --bind 0.0.0.0:8000