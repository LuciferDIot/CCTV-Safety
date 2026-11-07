FROM node:20-alpine AS builder

WORKDIR /app

RUN corepack enable && corepack prepare pnpm@latest --activate

# Copy dependency manifests
COPY frontend/package.json frontend/pnpm-lock.yaml frontend/pnpm-workspace.yaml* ./
RUN pnpm install --frozen-lockfile

# Copy source code and build Next.js application
COPY frontend/ ./
ENV NEXT_TELEMETRY_DISABLED=1
ENV BACKEND_URL=http://backend:8000
RUN pnpm build

EXPOSE 3000

ENV NODE_ENV=production
ENV PORT=3000
CMD ["pnpm", "start", "-p", "3000"]
