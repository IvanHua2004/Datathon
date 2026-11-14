# Règlement de comptes : interface Angular, construite puis servie par nginx

# Étape 1 : construction (Angular 22 exige Node ^22.22.3, ^24.15 ou >= 26)
FROM node:22-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY angular.json tsconfig.json ./
COPY src ./src
COPY public ./public
RUN npx ng build

# Étape 2 : nginx sert l'interface et relaie /api/ vers l'API Python
FROM nginx:alpine
COPY --from=build /app/dist/menu/browser/ /usr/share/nginx/html/
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s \
    CMD wget -q -O /dev/null http://localhost/ || exit 1
