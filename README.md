# YOSHA AI STUDIO

An Arabic-first creative production workspace that brings project management, media uploads, AI-assisted scripting, image generation, text-to-speech, transcription, subtitle export and basic MP4 rendering into one interface.

## Current release: MVP starter

This repository is an early working foundation, not a finished commercial platform. The current implementation includes:
- Next.js 14 frontend with a responsive Arabic RTL dashboard.
- FastAPI backend and SQLite persistence for projects and media metadata.
- Media upload and local media library.
- OpenAI adapters for script generation, image generation, speech generation and audio transcription.
- Kling AI 4.0 text-to-video integration with native 3–30 second clip tasks, selectable 720p/1080p/4K, HDR where supported, status polling, downloads and FFmpeg stitching into 1–4 minute MP4 films (requires a funded Kling API account).
- Basic FFmpeg editor actions: trim one uploaded video, merge 2–20 uploaded videos, transcode MP4 and burn subtitles.
- Audio/video transcription with timestamped segments and SRT subtitle export.
- Docker Compose for local development.

Not included yet: user accounts, billing, team collaboration, a professional multi-track timeline with transitions/keyframes, cloud object storage, background job queues, image/video/voice reference upload to Kling Omni, and robust cross-clip character continuity. Kling 4.0 generates 3–30 seconds per request. The long-form workflow splits a 1–4 minute request into multiple clips, then downloads and stitches them with FFmpeg. Continuity between separately generated clips is best-effort, not guaranteed. Kling API credentials and credits are required.

## Requirements

- Docker Desktop / Docker Engine with the Compose plugin.
- An OpenAI API key for AI features. The dashboard and project/media endpoints can be explored without one.

## Run locally

1. Clone the repository.
2. Copy `.env.example` to `.env`.
3. Add your key to `OPENAI_API_KEY` in `.env`.
4. Start the services:

```bash
docker compose up --build
```

5. Open the frontend at http://localhost:3000.
6. Open the API docs at http://localhost:8000/docs and health check at http://localhost:8000/health.

The API container stores uploaded media and its SQLite database in the persistent `yosha_storage` Docker volume. Do not commit a real `.env` file or API keys.

## Useful environment variables

| Variable | Purpose |
| --- | --- |
| `OPENAI_API_KEY` | Server-side OpenAI key; never expose it in browser code |
| `KLING_API_KEY` | Kling AI API key; never expose it in browser code |
| `KLING_API_BASE_URL` | Kling API region base URL |
| Kling output | Select 720p, 1080p or 4K; HDR is available at 1080p/4K where the account/model supports it |
| `OPENAI_TEXT_MODEL` | Text model used for scripts |
| `OPENAI_IMAGE_MODEL` | Image generation model |
| `OPENAI_TTS_MODEL` | Speech generation model |
| `OPENAI_STT_MODEL` | Transcription model |
| `CORS_ORIGINS` | Comma-separated allowed frontend origins |
| `NEXT_PUBLIC_API_URL` | API base URL used by the browser |

## API overview

- `GET /health`
- `GET, POST /api/projects`
- `DELETE /api/projects/{project_id}`
- `GET /api/media`
- `POST /api/media/upload`
- `POST /api/ai/script`
- `POST /api/ai/image`
- `POST /api/ai/video` (starts a 1–4 minute Kling film job)
- `GET /api/ai/video/{job_id}` (checks clip tasks, downloads and stitches the finished film)
- `POST /api/ai/voice`
- `POST /api/ai/transcribe/{media_id}`
- `POST /api/export/srt`
- `POST /api/render`
- `GET /api/integrations`

## Deploy on Render

The repository contains separate backend and frontend services.

### Backend (already deployed)

- Root Directory: `backend`
- Build Command: `pip install -r requirements.txt`
- Start Command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- Runtime: Python 3.11 (set `PYTHON_VERSION=3.11.11`)
- Required environment variables: `OPENAI_API_KEY`, `KLING_API_KEY`, and optionally `KLING_API_BASE_URL`.
- Health check: `/health`

The backend includes the FFmpeg executable through `imageio-ffmpeg`, so trim, merge, audio extraction and video stitching do not depend on an OS-level FFmpeg installation.

### Frontend (create as a separate Render Web Service)

- Root Directory: `frontend`
- Build Command: `npm install && npm run build`
- Start Command: `npm start`
- Environment variable: `NEXT_PUBLIC_API_URL=https://yosha-ai-studio.onrender.com`

After the frontend is deployed, set the backend's `CORS_ORIGINS` to the exact frontend URL if you want to restrict browser access to that origin. If omitted, the API permits cross-origin requests and does not enable credentialed cookies.

Important: Render's default filesystem is ephemeral. Uploaded media, generated files and the SQLite database can be lost when the service restarts or redeploys. Persistent production storage requires a persistent disk or an external database/object-storage integration; Supabase is not wired into this release yet.

## Security and deployment notes

This MVP is intended for local evaluation and controlled development. It currently has no authentication, authorization, rate limiting, malware scanning, or per-user storage isolation. Do not expose it publicly with private media or production credentials until those controls, HTTPS, backups, and deployment-specific CORS settings are implemented and tested.

## License

All rights reserved unless a separate license is added by the project owner.
