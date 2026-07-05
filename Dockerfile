# 基于 Python 3.9 镜像
FROM python:3.9-slim

# 设置工作目录
WORKDIR /app

# 复制项目文件
COPY . /app

# 暴露端口
EXPOSE 5000

# 启动服务器
CMD ["python", "server.py"]
