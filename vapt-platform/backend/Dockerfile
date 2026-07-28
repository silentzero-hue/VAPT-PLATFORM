FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        libpq-dev \
        curl \
        libxml2-dev \
        libxslt1-dev \
        libffi-dev \
        libssl-dev \
        libpango-1.0-0 \
        libpangoft2-1.0-0 \
        libreoffice \
        fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
RUN pip install --upgrade pip && pip install -e .

COPY . .

EXPOSE 8000 8081
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
