# Build stage
FROM node:20-alpine AS builder

WORKDIR /app

# Copy dependency specifications
COPY package*.json ./
RUN npm ci

# Copy source code and build SvelteKit app
COPY . .
RUN npm run build

# Run stage
FROM node:20-alpine

WORKDIR /app

# Install production dependencies only
COPY package*.json ./
RUN npm ci --omit=dev

# Copy compiled SvelteKit build from builder stage
COPY --from=builder /app/build ./build

# Environment configurations
ENV PORT=3000
ENV NODE_ENV=production

# Expose SvelteKit default runtime port
EXPOSE 3000

# Start Sveltekit Node adapter
CMD ["node", "build/index.js"]
