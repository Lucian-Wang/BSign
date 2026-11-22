FROM python:3.12-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY server/requirements.txt /app/server/requirements.txt
RUN pip install --no-cache-dir -r server/requirements.txt \
    && groupadd --gid 10001 bsign \
    && useradd --uid 10001 --gid 10001 --no-create-home bsign
COPY server /app/server
COPY app /app/app
USER 10001:10001
EXPOSE 8090
CMD ["python", "-m", "uvicorn", "server.run:app", "--host", "0.0.0.0", "--port", "8090", "--no-access-log", "--no-proxy-headers"]
