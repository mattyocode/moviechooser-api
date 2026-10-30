FROM python:3.12-slim-bookworm

WORKDIR /app

# set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1
ENV PIP_NO_CACHE_DIR off
ENV PIP_DISABLE_PIP_VERSION_CHECK on
ENV PIP_DEFAULT_TIMEOUT=100
ENV POETRY_VERSION 2.5.1
ARG SECRET_KEY=runtimetempsecretkey

# install system deps
RUN apt-get update \
  && apt-get -y install netcat-openbsd gcc postgresql \
  && apt-get clean

RUN pip install "poetry==$POETRY_VERSION"

COPY poetry.lock pyproject.toml /app/

RUN poetry config virtualenvs.create false \
  && poetry install --no-interaction --no-ansi

# bake the plot embedding model in, outside the ./app bind mount
ENV FASTEMBED_CACHE_PATH /opt/fastembed
RUN python -c "from fastembed import TextEmbedding; TextEmbedding('BAAI/bge-small-en-v1.5', cache_dir='/opt/fastembed')"

# copy entrypoint.sh
COPY ./entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

COPY . .

# run entrypoint.sh
ENTRYPOINT ["/app/entrypoint.sh"]

CMD gunicorn config.wsgi:application --bind 0.0.0.0:8000