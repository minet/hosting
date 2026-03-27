FROM node:22-alpine AS build
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm ci
COPY . .
ARG VITE_API_URL
ARG VITE_DNS_ZONE
ARG VITE_RESTRICTED_ROLES
ARG VITE_APP_ENV
ENV VITE_API_URL=$VITE_API_URL
ENV VITE_DNS_ZONE=$VITE_DNS_ZONE
ENV VITE_RESTRICTED_ROLES=$VITE_RESTRICTED_ROLES
ENV VITE_APP_ENV=$VITE_APP_ENV
RUN npm run build

FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
