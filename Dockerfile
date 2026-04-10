# Production Dockerfile — Cloud Run 최적화 (단일 스테이지 단순화)
FROM python:3.11-slim

WORKDIR /app

# 시스템 의존성 및 SSL 인증서 설치
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

# 시스템 전역에 직접 설치 (멀티스테이지 PATH 문제 방지)
RUN pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir gunicorn

# 앱 소스 복사
COPY . .

# 프로덕션 환경 변수
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Cloud Run은 PORT 환경변수로 포트를 동적 주입합니다 (기본 8080)
# CMD는 shell form을 사용해야 $PORT 변수가 런타임에 올바르게 치환됩니다.
CMD exec gunicorn -k uvicorn.workers.UvicornWorker -b 0.0.0.0:${PORT:-8080} --workers 2 app.main:app
