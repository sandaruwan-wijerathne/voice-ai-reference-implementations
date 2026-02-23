FROM 157129355835.dkr.ecr.eu-west-1.amazonaws.com/docker-hub/library/node:20-slim AS builder

WORKDIR /app

COPY package.json ./
RUN npm install --no-package-lock

COPY . .

ARG VITE_WS_URL=wss://vsvoice-demo.vetstoria.space/voice/browser/media-stream
ENV VITE_WS_URL=$VITE_WS_URL

RUN npm run build

FROM 157129355835.dkr.ecr.eu-west-1.amazonaws.com/docker-hub/library/nginx:alpine

COPY --from=builder /app/dist /usr/share/nginx/html

# Copy custom nginx configuration
COPY nginx.conf /etc/nginx/conf.d/default.conf

#entrypoint script
COPY scripts/docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD wget --no-verbose --tries=1 --spider http://localhost/ || exit 1

ENTRYPOINT ["/docker-entrypoint.sh"]
