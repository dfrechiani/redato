# Builder stage
FROM node:18-alpine AS builder
WORKDIR /app

# Copy configuration files
COPY package*.json ./
COPY tsconfig*.json ./
COPY next.config.ts ./

# Install dependencies
RUN npm install --legacy-peer-deps

# Copy source files
COPY . .

# Set build-time variables
ENV NEXT_TELEMETRY_DISABLED 1
ENV NODE_ENV=production

# Build the application
RUN npm run build

# Runner stage
FROM node:18-alpine AS runner
WORKDIR /app

ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED 1
ENV PORT=8080

# Copy necessary files
COPY --from=builder /app/public ./public
COPY --from=builder /app/package*.json ./
COPY --from=builder /app/next.config.ts ./
COPY --from=builder /app/.next/static ./.next/static
COPY --from=builder /app/.next/standalone ./

# Create a script to inject environment variables at runtime
RUN echo "#!/bin/sh" > /app/env.sh && \
    echo "echo \"window.ENV = {" >> /app/env.sh && \
    echo "  NEXT_PUBLIC_FIREBASE_API_KEY: '$NEXT_PUBLIC_FIREBASE_API_KEY'," >> /app/env.sh && \
    echo "  NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN: '$NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN'," >> /app/env.sh && \
    echo "  NEXT_PUBLIC_FIREBASE_PROJECT_ID: '$NEXT_PUBLIC_FIREBASE_PROJECT_ID'," >> /app/env.sh && \
    echo "  NEXT_PUBLIC_FIREBASE_STORAGE_BUCKET: '$NEXT_PUBLIC_FIREBASE_STORAGE_BUCKET'," >> /app/env.sh && \
    echo "  NEXT_PUBLIC_FIREBASE_MESSAGING_SENDER_ID: '$NEXT_PUBLIC_FIREBASE_MESSAGING_SENDER_ID'," >> /app/env.sh && \
    echo "  NEXT_PUBLIC_FIREBASE_APP_ID: '$NEXT_PUBLIC_FIREBASE_APP_ID'" >> /app/env.sh && \
    echo "}\" > /app/public/env-config.js" >> /app/env.sh && \
    chmod +x /app/env.sh

EXPOSE 8080

# Start script that injects env vars and starts the server
CMD ["/bin/sh", "-c", "/app/env.sh && node server.js"]
