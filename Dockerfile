FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt ./
RUN apt-get update \
	&& apt-get install -y --no-install-recommends \
		build-essential \
		gcc \
		libpq-dev \
		libffi-dev \
		libcairo2-dev \
		libjpeg62-turbo-dev \
		zlib1g-dev \
	&& rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir --upgrade pip setuptools wheel \
	&& pip install --no-cache-dir --prefer-binary -r requirements.txt

COPY app ./app
COPY worker.py ./worker.py

ENV PYTHONUNBUFFERED=1
EXPOSE 8000

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
