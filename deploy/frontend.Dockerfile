FROM node:22-bookworm-slim AS build
WORKDIR /app/src/frontend
COPY src/frontend/package.json src/frontend/package-lock.json ./
RUN --mount=type=cache,target=/root/.npm npm ci
COPY src/frontend ./
# prebuild exports only accepted publication plans into public/character-journal.
COPY src/data/character-journal/characters /app/src/data/character-journal/characters
RUN npm run build

FROM nginx:stable-alpine AS runtime
COPY deploy/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/src/frontend/dist /usr/share/nginx/html
EXPOSE 8080
