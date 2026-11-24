import os
import httpx

BASE_URL = "https://api.dev.runwayml.com"
API_VERSION = "2024-11-06"

def _headers():
    key = os.getenv("RUNWAYML_API_SECRET", "").strip()
    if not key:
        raise RuntimeError("RUNWAYML_API_SECRET is not configured on the server.")
    return {
        "Authorization": f"Bearer {key}",
        "X-Runway-Version": API_VERSION,
        "Content-Type": "application/json",
    }

async def create_video(prompt: str, duration: int = 5, ratio: str = "1280:720", model: str = "gen4.5"):
    payload = {"model": model, "promptText": prompt, "ratio": ratio, "duration": duration}
    async with httpx.AsyncClient(timeout=60) as client:
        response = await client.post(f"{BASE_URL}/v1/text_to_video", headers=_headers(), json=payload)
    if response.is_error:
        raise RuntimeError(f"Runway API {response.status_code}: {response.text[:1200]}")
    return response.json()

async def get_video_task(task_id: str):
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.get(f"{BASE_URL}/v1/tasks/{task_id}", headers=_headers())
    if response.is_error:
        raise RuntimeError(f"Runway API {response.status_code}: {response.text[:1200]}")
    return response.json()
