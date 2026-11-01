# Рабочая локальная CRM использует текущие исходники и данные через явный bind mount.
# Секреты, БД и медиа в образ не включаются.
FROM python:3.14-slim@sha256:cd89c30eda26ee911a4611b18680086e0ea42e6f5f8cbe653d07fa7958c9cec8
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && useradd --uid 10001 --create-home resource-local
USER 10001:10001
CMD ["python", "-u", "-m", "GameBAT_CRM.container_runtime"]
