# YOSHA AI STUDIO

An Arabic-first creative production workspace that brings project management, media uploads, AI-assisted scripting, image generation, text-to-speech, transcription, subtitle export and basic MP4 rendering into one interface.

## Current release: MVP starter

This repository is an early working foundation, not a finished commercial platform. The current implementation includes:
- Next.js 14 frontend with a responsive Arabic RTL dashboard.
- FastAPI backend and SQLite persistence for projects and media metadata.
- Media upload and local media library.
- OpenAI adapters for script generation, image generation, speech generation and audio transcription.
- Runway Dev text-to-video adapter with task creation, status polling and generated-video preview (requires a funded Runway API project).
- FFmpeg-based video conversion and SRT subtitle export.
- Docker Compose for local development.

Not included yet: user accounts, billing, team collaboration, a full multi-track editing timeline, cloud storage, background job queues, and automatic long-form multi-scene video assembly. The current Runway integration generates short clips (2–10 seconds per request) and requires provider credentials.

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
| `RUNWAYML_API_SECRET` | Runway Dev video-generation key; never expose it in browser code |
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
- `POST /api/ai/video` (starts a short text-to-video generation task)
- `GET /api/ai/video/{task_id}` (checks generation status and returns the output URL when ready)
- `POST /api/ai/voice`
- `POST /api/ai/transcribe/{media_id}`
- `POST /api/export/srt`
- `POST /api/render`
- `GET /api/integrations`

## Security and deployment notes

This MVP is intended for local evaluation and controlled development. It currently has no authentication, authorization, rate limiting, malware scanning, or per-user storage isolation. Do not expose it publicly with private media or production credentials until those controls, HTTPS, backups, and deployment-specific CORS settings are implemented and tested.

## License

All rights reserved unless a separate license is added by the project owner.
