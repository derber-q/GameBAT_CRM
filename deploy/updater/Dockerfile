# Контекст создаётся git archive: без .git, рабочих БД, outputs, ключей и медиа.
FROM python:3.14-slim@sha256:cd89c30eda26ee911a4611b18680086e0ea42e6f5f8cbe653d07fa7958c9cec8
ARG RELEASE_SHA
ARG SCHEMA_SHA
LABEL org.opencontainers.image.source="https://github.com/derber-q/GameBAT_CRM" \
      org.opencontainers.image.revision="$RELEASE_SHA" com.resource.schema="$SCHEMA_SHA"
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt ./
COPY deploy/updater/requirements.txt deploy/updater/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt -r deploy/updater/requirements.txt && useradd --uid 10001 --create-home resource
COPY . .
USER 10001:10001
ENV GAMEBAT_RELEASE_SHA=$RELEASE_SHA
CMD ["gunicorn","GameBAT_CRM.wsgi:application","--bind","0.0.0.0:8000","--workers","2","--timeout","120","--access-logfile","-"]
