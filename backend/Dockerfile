# ---------- SkillQuest AI 后端镜像 ----------
FROM python:3.12-slim

# 环境变量
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# 系统依赖
RUN apt-get update \
    && apt-get install -y --no-install-recommends gcc default-libmysqlclient-dev curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 先装依赖以利用 Docker 层缓存
COPY requirements.txt .
RUN pip install -r requirements.txt

# 复制业务代码
COPY . .

# 供 docker-compose 覆盖的默认启动参数
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]