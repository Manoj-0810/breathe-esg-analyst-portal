# Multi-stage production-grade Dockerfile for Vite React Frontend
# ----------------------------------------------------------------------

# Stage 1: Build the React Application
FROM node:18-alpine AS builder

WORKDIR /app

# Copy package catalogs
COPY package.json package-lock.json ./

# Install dependencies
RUN npm ci

# Copy application files
COPY . .

# Setup build-time arguments (Vite reads these during compilation)
ARG VITE_API_URL
ENV VITE_API_URL=$VITE_API_URL

# Compile the optimized React production bundle
RUN npm run build


# Stage 2: Serve compiled bundle via Nginx
FROM nginx:stable-alpine AS runner

# Remove standard placeholder contents
RUN rm -rf /usr/share/nginx/html/*

# Copy built distribution files from builder stage
COPY --from=builder /app/dist /usr/share/nginx/html

# Inject customized Nginx server block configuration
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Expose standard container port
EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
