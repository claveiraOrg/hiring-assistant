FROM node:20-alpine AS builder
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm ci
COPY . .

ARG VITE_HIREMATCH_API_URL=http://localhost:8001
ARG VITE_HIREMATCH_API_KEY=dev-secret-key
ENV VITE_HIREMATCH_API_URL=$VITE_HIREMATCH_API_URL
ENV VITE_HIREMATCH_API_KEY=$VITE_HIREMATCH_API_KEY

RUN npm run build

FROM nginx:alpine
COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 3000
CMD ["nginx", "-g", "daemon off;"]
