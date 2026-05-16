# syntax=docker/dockerfile:1.6
#
# Next.js dashboard. Three stages: deps → build → runtime. Built with the
# `./dashboard` directory as the docker context (see docker-compose).
#
# We use `next start` rather than `next dev` so the prod parity is real
# (server components are pre-rendered, source maps stripped). Set
# NEXT_PUBLIC_API_URL at build time because Next inlines it into the
# client bundle — changing it at runtime requires a rebuild.

# ─── deps ─────────────────────────────────────────────────────────────
FROM node:22-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm ci --no-audit --no-fund


# ─── build ────────────────────────────────────────────────────────────
FROM node:22-alpine AS build
WORKDIR /app
ENV NEXT_TELEMETRY_DISABLED=1
ARG NEXT_PUBLIC_API_URL=http://api:8000/api/v1
ENV NEXT_PUBLIC_API_URL=${NEXT_PUBLIC_API_URL}
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN npm run build


# ─── runtime ──────────────────────────────────────────────────────────
FROM node:22-alpine AS runtime
WORKDIR /app
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1 PORT=3000

RUN addgroup -g 10003 next && adduser -D -u 10003 -G next next

COPY --from=build --chown=next:next /app/public ./public
COPY --from=build --chown=next:next /app/.next ./.next
COPY --from=build --chown=next:next /app/node_modules ./node_modules
COPY --from=build --chown=next:next /app/package.json ./package.json

USER next
EXPOSE 3000

HEALTHCHECK --interval=15s --timeout=3s --start-period=30s --retries=3 \
  CMD wget -qO- http://localhost:3000/ || exit 1

CMD ["npm", "run", "start"]
