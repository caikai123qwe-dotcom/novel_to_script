FROM python:3.11-slim

# 设置工作目录
WORKDIR /app

# 设置环境变量，确保 Python 输出直接打印到控制台，不进行缓存
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# 安装系统依赖（如果有些库编译需要 gcc）
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件并安装
COPY requirements.txt .
# 使用清华源加速下载
RUN pip install --no-cache-dir -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# 复制后端所有源码
COPY . .

# 暴露 FastAPI 默认端口
EXPOSE 8000

# 启动命令
CMD ["uvicorn", "Main:app", "--host", "0.0.0.0", "--port", "8000"]
