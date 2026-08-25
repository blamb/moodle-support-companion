# Stage 1: Build the frontend
FROM node:22-slim AS frontend-build
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm install
COPY frontend/ ./
RUN npm run build

# Stage 2: Python backend + built frontend
FROM python:3.13-slim
WORKDIR /app

# Install backend dependencies
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend code
COPY backend/ ./backend/

# Build the knowledge-base vector index at image-build time.
# The runtime instance has a throttled CPU and NO persistent volume, so embedding
# at runtime is slow (~60-90 min) and would be wiped on every redeploy. Building
# here bakes a ready-to-use index into the image: the container boots with the
# knowledge base already populated and never has to embed at runtime. This also
# pre-caches the sentence-transformer model used for query embeddings.
# The assertion fails the build (rather than shipping an empty KB) if no sources
# were found.
RUN cd backend && python -c "from app.ingestion.pipeline import run_ingestion; s = run_ingestion(); print('Built index:', s.get('total_chunks'), 'chunks from', s.get('sources_ingested')); assert (s.get('total_chunks') or 0) > 100, 'Index build produced too few chunks — check knowledge sources'"

# Copy built frontend from stage 1
COPY --from=frontend-build /app/frontend/dist ./frontend/dist

# Railway sets PORT automatically
ENV PORT=8000
EXPOSE 8000

# Start the server
CMD ["sh", "-c", "cd backend && python -m uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]
