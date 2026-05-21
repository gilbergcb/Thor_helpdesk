FROM node:22-alpine AS build

WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm install
COPY . .
ARG VITE_API_URL=/api/v1
ENV VITE_API_URL=$VITE_API_URL
RUN npm run build

# F-14 Phase 4.2: nginx-unprivileged escuta em 8080 e roda como uid 101
# (nginx) sem CAP_NET_BIND_SERVICE — sem root no runtime.
FROM nginxinc/nginx-unprivileged:1.27-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
# F-16: snippet de security headers em /etc/nginx/snippets para nao
# ser auto-carregado por conf.d/*.conf (so include explicito).
USER root
RUN mkdir -p /etc/nginx/snippets
USER nginx
COPY security-headers.conf /etc/nginx/snippets/security-headers.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 8080
