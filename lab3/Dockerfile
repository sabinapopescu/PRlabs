FROM node:22

WORKDIR /app
COPY package*.json ./

# Install dependencies
RUN npm install

COPY . .

# Build TypeScript
RUN npm run compile

# Expose the port 
EXPOSE 8080

# Start the server
CMD ["node", "--require", "source-map-support/register", "dist/src/server.js", "8080", "boards/perfect.txt"]