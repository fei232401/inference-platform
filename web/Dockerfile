FROM node:22-alpine AS build

WORKDIR /app

ARG NPM_REGISTRY=https://registry.npmjs.org
ARG GIT_SHA=unknown

RUN npm config set registry ${NPM_REGISTRY}

COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund

COPY tsconfig.json vite.config.ts index.html ./
COPY src ./src

RUN VITE_BUILD_VERSION=${GIT_SHA} npm run build

FROM nginx:1.27-alpine

ARG GIT_SHA=unknown

LABEL org.opencontainers.image.revision=${GIT_SHA}

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80
