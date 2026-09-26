# ---------- SkillQuest AI 前端镜像（多阶段构建） ----------
# 阶段一：构建静态资源
FROM node:20-alpine AS builder

WORKDIR /app

COPY package.json ./
RUN npm install --registry=https://registry.npmmirror.com

COPY . .
RUN npm run build

# 阶段二：Nginx 托管
FROM nginx:1.27-alpine

# 自定义 nginx 配置（含 /api 反向代理到后端服务）
COPY nginx.conf /etc/nginx/conf.d/default.conf

# 复制构建产物
COPY --from=builder /app/dist /usr/share/nginx/html

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]