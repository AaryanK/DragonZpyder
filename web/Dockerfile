# React/Vite is a Node.js build; Python remains the only production HTTP server.
FROM node:22-alpine AS frontend
WORKDIR /src
COPY frontend/package.json frontend/package.json
RUN npm install --prefix frontend --no-audit --no-fund --package-lock=false
COPY . .
RUN npm run build --prefix frontend && npm run test --prefix frontend

FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt \
    && useradd --create-home --uid 10001 dragonzpyder
COPY . /app
COPY --from=frontend /src/dist /app/dist
RUN chown -R dragonzpyder:dragonzpyder /app
USER dragonzpyder
EXPOSE 8080
CMD ["sh", "-c", "exec uvicorn main:app --host 0.0.0.0 --port ${PORT:-8080}"]
