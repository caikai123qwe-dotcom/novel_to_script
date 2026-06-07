FROM python:3.11-slim

# 设置工作目录
WORKDIR /app

ENV PYTHONUNBUFFERED=1

# 安装依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# 复制前端所有源码
COPY . .

# 暴露 Streamlit 默认端口
EXPOSE 8501

# 启动命令（绑定 0.0.0.0 允许外部访问）
CMD ["streamlit", "run", "app.py", "--server.port", "8501", "--server.address", "0.0.0.0"]
