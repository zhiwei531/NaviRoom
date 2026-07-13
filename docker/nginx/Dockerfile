# ============================================================
# NaviRoom 生产环境 Nginx 反向代理
# ============================================================
FROM nginx:alpine

# 复制站点配置
COPY docker/nginx/nginx.conf /etc/nginx/conf.d/default.conf

# 健康检查
HEALTHCHECK --interval=30s --timeout=3s \
    CMD wget -qO- http://localhost:80/healthz || exit 1

EXPOSE 80 443

CMD ["nginx", "-g", "daemon off;"]
