# The frontend image: the Vite build served by nginx, which also proxies /api to the backend (one origin, so
# the browser needs no CORS). Built by docker compose with frontend/ as the context (see frontend/.dockerignore).
#
#   docker compose build frontend && docker compose up -d --wait   ->  http://localhost:8080

# --- build: install the locked packages, check types, bundle --------------------------------------------------
FROM node:24-alpine AS build
WORKDIR /app
COPY package.json package-lock.json .npmrc ./
RUN npm ci --no-audit --no-fund
COPY . .
RUN npm run build

# --- serve: unprivileged nginx (runs as user nginx, listens on 8080) -------------------------------------------
FROM nginxinc/nginx-unprivileged:1.28-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD wget -q -O /dev/null http://127.0.0.1:8080/ || exit 1
