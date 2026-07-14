# 直接使用 nginx，不需要 node、不需要 npm install、不需要 build
FROM nginx:1.25-alpine AS production-stage

# 安装 curl 用于健康检查
#RUN apk add --no-cache curl

# 直接复制服务器上已经打包好的 dist 文件夹
COPY ./dist /usr/share/nginx/html

# 复制 nginx 配置文件
COPY nginx.conf /etc/nginx/conf.d/default.conf

# 暴露端口
EXPOSE 80

# 健康检查
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:80/health || exit 1

# 使用 nginx 默认启动命令
CMD ["nginx", "-g", "daemon off;"]
