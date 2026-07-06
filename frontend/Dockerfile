# 构建阶段
FROM node:18-alpine AS build-stage

# 设置工作目录
WORKDIR /app

# 复制package文件
COPY package*.json ./

# 安装依赖
RUN npm ci --silent

# 复制源代码
COPY . .

# 构建应用（跳过类型检查）
RUN npm run build-only

# 生产阶段
FROM nginx:1.25-alpine AS production-stage

# 安装curl用于健康检查
RUN apk add --no-cache curl

# 复制构建结果
COPY --from=build-stage /app/dist /usr/share/nginx/html

# 复制nginx配置文件
COPY nginx.conf /etc/nginx/conf.d/default.conf

# 暴露端口
EXPOSE 80

# 健康检查
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:80/health || exit 1

# 使用nginx默认启动命令
CMD ["nginx", "-g", "daemon off;"]