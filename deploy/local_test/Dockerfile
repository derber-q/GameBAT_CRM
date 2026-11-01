# Только изолированная тестовая CRM; production использует отдельный будущий этап B.
FROM python:3.14-slim@sha256:cd89c30eda26ee911a4611b18680086e0ea42e6f5f8cbe653d07fa7958c9cec8
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN useradd --uid 10001 --create-home resource-test && mkdir -p /app/outputs/local_test && chown -R 10001:10001 /app/outputs
USER 10001:10001
ENV GAMEBAT_TEST_ROOT=/app/outputs/local_test/container
CMD ["python", "-m", "GameBAT_CRM.local_test", "check"]
