FROM python:3.11-slim

WORKDIR /app

# 安装编译工具（部分 Python 包需要）+ LibreOffice（docx→PDF）+ 中文字体（否则中文 PDF 乱码）
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libffi-dev \
    libreoffice-writer \
    fonts-noto-cjk \
    && rm -rf /var/lib/apt/lists/*

# 先装依赖（利用缓存，改代码不用重装）
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制项目代码
COPY . .

# 修复 Windows 换行符 + 给执行权限
RUN sed -i 's/\r$//' entrypoint.sh && chmod +x entrypoint.sh

# 创建上传目录
RUN mkdir -p /app/uploads

EXPOSE 8000

ENTRYPOINT ["./entrypoint.sh"]