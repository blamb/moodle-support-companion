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

# Build the knowledge-base vector index at image-build time into a FIXED path
# (/app/prebuilt_data), independent of the runtime data dir.
# The runtime instance has a throttled CPU, so embedding at runtime is slow
# (~60-90 min). Building here bakes a ready-to-use index into the image; on
# startup the app seeds the runtime store from it (see main._seed_knowledge_base),
# so the container boots with the knowledge base ready and never embeds at
# runtime. RAILWAY_VOLUME_MOUNT_PATH is set for this step so config.DATA_DIR
# resolves to the same fixed path the startup seed reads from
# (config.PREBUILT_CHROMA_DIR). Also pre-caches the sentence-transformer model.
# The assertion fails the build (rather than shipping an empty KB) if no sources
# were found.
RUN cd backend && RAILWAY_VOLUME_MOUNT_PATH=/app/prebuilt_data python -c "from app.ingestion.pipeline import run_ingestion; s = run_ingestion(); print('Built index:', s.get('total_chunks'), 'chunks from', s.get('sources_ingested')); assert (s.get('total_chunks') or 0) > 100, 'Index build produced too few chunks — check knowledge sources'"

# Copy built frontend from stage 1
COPY --from=frontend-build /app/frontend/dist ./frontend/dist

# Railway sets PORT automatically
ENV PORT=8000
EXPOSE 8000

# Start the server
CMD ["sh", "-c", "cd backend && python -m uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]
