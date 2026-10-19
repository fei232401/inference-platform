FROM python:3.11-slim

ARG PIP_INDEX_URL=https://pypi.org/simple
ARG GIT_SHA=unknown

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    APP_VERSION=${GIT_SHA}

WORKDIR /app

COPY services/router/requirements.txt ./
RUN pip install --no-cache-dir --index-url "${PIP_INDEX_URL}" -r requirements.txt

COPY services/router/src ./src
COPY ops ./ops

EXPOSE 8000

USER 1000

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
