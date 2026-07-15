FROM node:24-alpine AS build

WORKDIR /app
COPY src/apps/web/package.json src/apps/web/package-lock.json ./
RUN npm ci
COPY src/apps/web/ ./
RUN npm run build

FROM nginx:1.27-alpine
COPY src/infra/compose/nginx/base-spark.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80
HEALTHCHECK --interval=10s --timeout=3s --retries=5 \
  CMD wget -q -O - http://127.0.0.1:8088/healthz || exit 1
