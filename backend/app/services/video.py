import os
import httpx

BASE_URL = os.getenv("KLING_API_BASE_URL", "https://api-singapore.klingai.com").rstrip("/")
MODEL_PATH = "/text-to-video/kling-4.0"

def _headers():
    key = os.getenv("KLING_API_KEY", "").strip()
    if not key:
        raise RuntimeError("KLING_API_KEY is not configured on the server.")
    return {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}

def split_duration(total: int) -> list[int]:
    if total < 60 or total > 240:
        raise ValueError("Video duration must be between 60 and 240 seconds.")
    count = (total + 29) // 30
    base, extra = divmod(total, count)
    parts = [base + (1 if i < extra else 0) for i in range(count)]
    if any(p < 3 or p > 30 for p in parts):
        raise ValueError("Unable to split requested duration into Kling-compatible clips.")
    return parts

async def create_clip(prompt: str, duration: int, ratio: str, resolution: str = "1080p", dynamic_range: str = "sdr"):
    if duration < 3 or duration > 30:
        raise ValueError("Kling 4.0 supports 3–30 seconds per clip.")
    if resolution not in ("720p", "1080p", "4k"):
        raise ValueError("Unsupported Kling resolution.")
    if dynamic_range not in ("sdr", "hdr"):
        raise ValueError("Unsupported dynamic range.")
    if dynamic_range == "hdr" and resolution == "720p":
        raise ValueError("HDR requires 1080p or 4K output.")
    settings = {"duration": duration, "resolution": resolution, "aspect_ratio": ratio}
    if resolution in ("1080p", "4k"):
        settings["dynamic_range"] = dynamic_range
    payload = {
        "prompt": prompt,
        "settings": settings,
        "options": {"watermark_info": {"enabled": False}},
    }
    async with httpx.AsyncClient(timeout=60) as client:
        response = await client.post(f"{BASE_URL}{MODEL_PATH}", headers=_headers(), json=payload)
    if response.is_error:
        raise RuntimeError(f"Kling API {response.status_code}: {response.text[:1200]}")
    data = response.json()
    if data.get("code") != 0 or not data.get("data", {}).get("id"):
        raise RuntimeError(f"Kling API rejected the task: {str(data)[:1200]}")
    return data["data"]

async def get_clip(task_id: str):
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.get(f"{BASE_URL}/tasks", headers=_headers(), params={"task_ids": task_id})
    if response.is_error:
        raise RuntimeError(f"Kling API {response.status_code}: {response.text[:1200]}")
    data = response.json()
    if data.get("code") != 0:
        raise RuntimeError(f"Kling task query failed: {str(data)[:1200]}")
    tasks = data.get("data") or []
    if isinstance(tasks, dict):
        tasks = tasks.get("result") or []
    if not tasks:
        raise RuntimeError("Kling returned no task data.")
    return next((task for task in tasks if task.get("id") == task_id), tasks[0])

async def download_clip(url: str, destination: str):
    async with httpx.AsyncClient(timeout=240, follow_redirects=True) as client:
        async with client.stream("GET", url) as response:
            response.raise_for_status()
            with open(destination, "wb") as f:
                async for chunk in response.aiter_bytes():
                    f.write(chunk)
