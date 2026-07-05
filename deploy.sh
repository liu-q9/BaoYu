#!/bin/bash
# 鲍鱼数据分析系统 - 云服务器部署脚本
# 用法: bash deploy.sh

echo "===== 鲍鱼数据分析系统 部署脚本 ====="

# 1. 安装Python依赖
echo "[1/4] 安装Python依赖..."
pip install -r requirements.txt

# 2. 初始化数据库（首次运行自动创建）
echo "[2/4] 数据库初始化（首次运行自动创建）..."

# 3. 开放防火墙端口
echo "[3/4] 开放防火墙端口 5000..."
if command -v firewall-cmd &> /dev/null; then
    sudo firewall-cmd --add-port=5000/tcp --permanent
    sudo firewall-cmd --reload
elif command -v ufw &> /dev/null; then
    sudo ufw allow 5000/tcp
else
    echo "  - 请手动开放云服务器安全组端口 5000"
fi

# 4. 启动服务器（后台运行）
echo "[4/4] 启动服务器..."
nohup python server.py > server.log 2>&1 &
echo "服务器已启动，访问 http://<服务器公网IP>:5000"
echo "日志文件: server.log"
