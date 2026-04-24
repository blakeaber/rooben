# ── Rooben dashboard — Next.js 15 production image ───────────────────────────
# Two-stage build. The final stage keeps node_modules so the same image can
# serve either `next start` (production, default) or `next dev` (dev overlay).

FROM node:20-alpine AS builder
WORKDIR /app
ENV NEXT_TELEMETRY_DISABLED=1

# Next.js inlines process.env into the build output for rewrites(), so the
# API proxy target must be set BEFORE `npm run build`. `http://api:8420`
# assumes this image runs inside the Rooben docker-compose stack alongside
# the `api` service. For other deployments, override NEXT_INTERNAL_API_URL
# at build with --build-arg.
ARG NEXT_INTERNAL_API_URL=http://api:8420
ENV NEXT_INTERNAL_API_URL=$NEXT_INTERNAL_API_URL

COPY package.json package-lock.json ./
RUN npm ci

COPY . .
RUN npm run build

FROM node:20-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1

RUN apk add --no-cache wget

COPY --from=builder /app/.next ./.next
COPY --from=builder /app/public ./public
COPY --from=builder /app/package.json ./package.json
COPY --from=builder /app/package-lock.json ./package-lock.json
COPY --from=builder /app/next.config.ts ./next.config.ts
COPY --from=builder /app/tsconfig.json ./tsconfig.json
COPY --from=builder /app/node_modules ./node_modules
COPY --from=builder /app/src ./src

EXPOSE 3000

HEALTHCHECK --interval=10s --timeout=3s --retries=10 \
  CMD wget -qO- http://localhost:3000/ >/dev/null 2>&1 || exit 1

CMD ["npm", "start"]
