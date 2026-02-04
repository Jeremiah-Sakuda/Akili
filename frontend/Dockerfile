# Akili frontend — dev server with proxy to API
# Use Node 20 LTS
FROM node:20-alpine

WORKDIR /app

COPY package*.json ./

RUN npm ci 2>/dev/null || npm install

COPY . .

# VITE_PROXY_TARGET is set in docker-compose to http://api:8000
EXPOSE 3000

CMD ["npm", "run", "dev"]
