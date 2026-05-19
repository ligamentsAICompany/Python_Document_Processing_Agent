FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8080 \
    PAGEINDEX_REPO=/app/PageIndex \
    DATA_DIR=/tmp/data \
    GCP_PROJECT_ID=ligaments-portal \
    GCS_BUCKET=rocket_uploaded_files

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt requirements-pageindex.txt ./
RUN python -m pip install --no-cache-dir --upgrade pip \
    && python -m pip install --no-cache-dir -r requirements.txt \
    && if [ -s requirements-pageindex.txt ]; then python -m pip install --no-cache-dir -r requirements-pageindex.txt; fi

RUN git clone --depth 1 https://github.com/VectifyAI/PageIndex.git /app/PageIndex

COPY app ./app

RUN mkdir -p /tmp/data/uploads /tmp/data/indexes /tmp/data/sessions

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
