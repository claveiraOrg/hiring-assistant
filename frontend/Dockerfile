FROM oven/bun:latest AS builder
WORKDIR /app
COPY package.json bun.lock* ./
RUN bun install --frozen-lockfile
COPY . .

ARG VITE_API_URL=http://178.104.211.230:8001
ENV VITE_API_URL=$VITE_API_URL

RUN bun run build

FROM oven/bun:latest AS runner
WORKDIR /app
RUN bun add serve@14
COPY --from=builder /app/dist ./dist
EXPOSE 3000
CMD ["bunx", "serve", "-s", "dist", "-l", "3000"]

