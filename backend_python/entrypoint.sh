#!/bin/bash
set -e

# ===== 第一步：等待 MySQL 就绪 =====
echo "⏳ 等待 MySQL 就绪..."
python -c "
import time, pymysql, os, re, urllib.parse
url = os.environ['DATABASE_URL']
m = re.match(r'^mysql\+pymysql://([^:]+):([^@]*)@([^:/]+)(?::(\d+))?/([^?]*)(\?.*)?\$', url)
if not m:
    print('❌ DATABASE_URL 格式错误'); exit(1)
host, user = m.group(3), m.group(1)
pwd = urllib.parse.unquote(m.group(2))
port = int(m.group(4) or 3306)
for i in range(30):
    try:
        pymysql.connect(host=host, user=user, password=pwd, port=port)
        print('✅ MySQL 已就绪')
        break
    except Exception:
        print(f'  等待 MySQL... ({i+1}/30)')
        time.sleep(2)
else:
    print('❌ MySQL 连接超时，退出'); exit(1)
"

# ===== 第二步：初始化种子数据（菜单/角色/用户/AI模型）=====
echo "🌱 初始化种子数据..."
python seed.py || echo "⚠️ 种子数据已存在，跳过"

# ===== 第三步：启动 FastAPI 服务 =====
echo "🚀 启动 FastAPI 服务..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000