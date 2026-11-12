ARG PYTHON_IMAGE=python:3.13-slim
FROM ${PYTHON_IMAGE}
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_DISABLE_PIP_VERSION_CHECK=1 FITNESS_DATA_DIR=/data
WORKDIR /app/backend
COPY backend/requirements.lock /tmp/requirements.lock
RUN pip install --no-cache-dir -r /tmp/requirements.lock \
    && groupadd --gid 10001 fitness \
    && useradd --uid 10001 --gid fitness --no-create-home fitness \
    && mkdir -p /data && chown fitness:fitness /data
COPY backend/ /app/backend/
COPY frontend/dist/ /app/frontend/dist/
USER 10001:10001
EXPOSE 8000
CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--no-proxy-headers"]
