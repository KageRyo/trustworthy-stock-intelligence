FROM node:22.23.2-alpine

WORKDIR /app

COPY package*.json ./
RUN npm ci

COPY . .

EXPOSE 5175

CMD ["npm", "run", "dev"]
