import os, uuid, shutil, subprocess
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, PlainTextResponse
from pydantic import BaseModel
from sqlmodel import SQLModel, Field, Session, create_engine, select
from .services.ai import generate_script, generate_image, generate_speech, transcribe
from .services.video import create_video, get_video_task

BASE = Path(__file__).resolve().parents[1]
STORAGE = Path(os.getenv("STORAGE_DIR", str(BASE / "storage"))).resolve()
UPLOADS, OUTPUTS = STORAGE / "uploads", STORAGE / "outputs"
UPLOADS.mkdir(parents=True, exist_ok=True); OUTPUTS.mkdir(parents=True, exist_ok=True)
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{STORAGE / 'yosha.db'}")
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {})

class Project(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    title: str
    description: str = ""
    status: str = "draft"
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
class Media(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    project_id: Optional[int] = None
    filename: str
    original_name: str
    kind: str
    url: str
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
SQLModel.metadata.create_all(engine)

app = FastAPI(title="YOSHA AI STUDIO API", version="1.0.0")
origins = [v.strip() for v in os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",") if v.strip()]
app.add_middleware(CORSMiddleware, allow_origins=origins or ["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

class ProjectIn(BaseModel):
    title: str
    description: str = ""
class ScriptIn(BaseModel):
    prompt: str
    language: str = "Arabic"
    style: str = "cinematic"
class TextIn(BaseModel):
    text: str
    voice: str = "alloy"
class ImageIn(BaseModel):
    prompt: str
class VideoIn(BaseModel):
    prompt: str
    duration: int = 5
    ratio: str = "1280:720"
    model: str = "gen4.5"
class RenderIn(BaseModel):
    media_id: int
    subtitle_text: str = ""
    burn_subtitles: bool = False

@app.get("/health")
def health():
    return {"status":"ok","service":"YOSHA AI STUDIO","ai_configured":bool(os.getenv("OPENAI_API_KEY"))}
@app.get("/api/projects")
def projects():
    with Session(engine) as s: return s.exec(select(Project).order_by(Project.id.desc())).all()
@app.post("/api/projects")
def create_project(data: ProjectIn):
    if not data.title.strip(): raise HTTPException(400,"Project title is required")
    with Session(engine) as s:
        obj=Project(title=data.title.strip(),description=data.description.strip()); s.add(obj); s.commit(); s.refresh(obj); return obj
@app.delete("/api/projects/{project_id}")
def delete_project(project_id:int):
    with Session(engine) as s:
        obj=s.get(Project,project_id)
        if not obj: raise HTTPException(404,"Project not found")
        s.delete(obj); s.commit(); return {"deleted":True}
@app.get("/api/media")
def media(project_id:Optional[int]=None):
    with Session(engine) as s:
        q=select(Media).order_by(Media.id.desc())
        if project_id is not None: q=q.where(Media.project_id==project_id)
        return s.exec(q).all()
@app.post("/api/media/upload")
async def upload(file:UploadFile=File(...),project_id:Optional[int]=None):
    ext=Path(file.filename or "").suffix.lower()
    allowed={".mp4",".mov",".mkv",".webm",".mp3",".wav",".m4a",".png",".jpg",".jpeg",".webp"}
    if ext not in allowed: raise HTTPException(415,"Unsupported file type")
    name=f"{uuid.uuid4().hex}{ext}"; dest=UPLOADS/name
    with dest.open("wb") as out: shutil.copyfileobj(file.file,out)
    kind="video" if ext in {".mp4",".mov",".mkv",".webm"} else "audio" if ext in {".mp3",".wav",".m4a"} else "image"
    with Session(engine) as s:
        obj=Media(project_id=project_id,filename=name,original_name=file.filename or name,kind=kind,url=f"/media/{name}")
        s.add(obj); s.commit(); s.refresh(obj); return obj
@app.get("/media/{filename}")
def get_media(filename:str):
    path=(UPLOADS/filename).resolve()
    if path.parent!=UPLOADS.resolve() or not path.is_file(): raise HTTPException(404,"Media not found")
    return FileResponse(path)
@app.get("/outputs/{filename}")
def get_output(filename:str):
    path=(OUTPUTS/filename).resolve()
    if path.parent!=OUTPUTS.resolve() or not path.is_file(): raise HTTPException(404,"Output not found")
    return FileResponse(path)
@app.post("/api/ai/script")
def script(data:ScriptIn):
    try: return {"script":generate_script(data.prompt,data.language,data.style)}
    except Exception as e: raise HTTPException(502,str(e))
@app.post("/api/ai/image")
def image(data:ImageIn):
    try:
        name=f"image-{uuid.uuid4().hex}.png"; generate_image(data.prompt,OUTPUTS/name); return {"filename":name,"url":f"/outputs/{name}"}
    except Exception as e: raise HTTPException(502,str(e))
@app.post("/api/ai/voice")
def voice(data:TextIn):
    try:
        name=f"voice-{uuid.uuid4().hex}.mp3"; generate_speech(data.text,OUTPUTS/name,data.voice); return {"filename":name,"url":f"/outputs/{name}"}
    except Exception as e: raise HTTPException(502,str(e))
@app.post("/api/ai/transcribe/{media_id}")
def transcribe_media(media_id:int):
    with Session(engine) as s: obj=s.get(Media,media_id)
    if not obj: raise HTTPException(404,"Media not found")
    if obj.kind not in ("audio","video"): raise HTTPException(400,"Upload audio or video")
    src=UPLOADS/obj.filename; audio=src; temp=None
    if obj.kind=="video":
        temp=OUTPUTS/f"audio-{uuid.uuid4().hex}.mp3"
        proc=subprocess.run(["ffmpeg","-y","-i",str(src),"-vn","-acodec","mp3",str(temp)],capture_output=True)
        if proc.returncode: raise HTTPException(500,proc.stderr.decode(errors="ignore")[-1000:])
        audio=temp
    try: return transcribe(audio)
    except Exception as e: raise HTTPException(502,str(e))
    finally:
        if temp and temp.exists(): temp.unlink()
@app.post("/api/export/srt")
def export_srt(data:dict):
    def stamp(value):
        ms=int(max(0,float(value))*1000); h,r=divmod(ms,3600000); m,r=divmod(r,60000); sec,ms=divmod(r,1000)
        return f"{h:02}:{m:02}:{sec:02},{ms:03}"
    rows=[]
    for i,seg in enumerate(data.get("segments",[]),1):
        rows.extend([str(i),f"{stamp(seg.get('start',0))} --> {stamp(seg.get('end',0))}",str(seg.get("text","")).strip(),""])
    return PlainTextResponse("\n".join(rows),media_type="text/plain",headers={"Content-Disposition":"attachment; filename=yosha-subtitles.srt"})
@app.post("/api/render")
def render(data:RenderIn):
    with Session(engine) as s: obj=s.get(Media,data.media_id)
    if not obj or obj.kind!="video": raise HTTPException(400,"Choose an uploaded video")
    src=UPLOADS/obj.filename; name=f"render-{uuid.uuid4().hex}.mp4"; dest=OUTPUTS/name
    cmd=["ffmpeg","-y","-i",str(src)]
    temp=None
    if data.burn_subtitles and data.subtitle_text.strip():
        temp=OUTPUTS/f"{uuid.uuid4().hex}.srt"; temp.write_text(data.subtitle_text,encoding="utf-8")
        cmd += ["-vf",f"subtitles={temp.as_posix()}"]
    cmd += ["-c:v","libx264","-preset","veryfast","-crf","22","-c:a","aac","-movflags","+faststart",str(dest)]
    proc=subprocess.run(cmd,capture_output=True)
    if temp and temp.exists(): temp.unlink()
    if proc.returncode: raise HTTPException(500,proc.stderr.decode(errors="ignore")[-1800:])
    return {"filename":name,"url":f"/outputs/{name}"}
@app.get("/api/integrations")
def integrations():
    return [
      {"name":"OpenAI","category":"Text / Image / Voice / Transcription","status":"connected" if os.getenv("OPENAI_API_KEY") else "needs_api_key","features":["script","image","voice","transcription"]},
      {"name":"FFmpeg","category":"Video processing / MP4 export","status":"available","features":["render","burn subtitles","transcode"]},
      {"name":"Runway / Kling / Veo","category":"Generative video","status":"adapter_required","features":["text-to-video","image-to-video"],"note":"Provider credentials and official API adapter required."},
      {"name":"ElevenLabs","category":"Voice / dubbing","status":"adapter_required","features":["multilingual dubbing"]}]


@app.post("/api/ai/video")
async def ai_video(data: VideoIn):
    if not data.prompt.strip(): raise HTTPException(400, "Video prompt is required")
    if len(data.prompt) > 1000: raise HTTPException(400, "Prompt must be 1000 characters or fewer")
    if data.duration < 2 or data.duration > 10: raise HTTPException(400, "Duration must be between 2 and 10 seconds")
    if data.ratio not in ("1280:720", "720:1280"): raise HTTPException(400, "Unsupported aspect ratio")
    try:
        task = await create_video(data.prompt.strip(), data.duration, data.ratio, data.model)
        return {"task_id": task.get("id"), "status": task.get("status", "PENDING"), "estimated_cost": task.get("estimatedCost")}
    except Exception as e: raise HTTPException(502, str(e))

@app.get("/api/ai/video/{task_id}")
async def ai_video_status(task_id: str):
    try:
        task = await get_video_task(task_id)
        status = task.get("status", "UNKNOWN")
        output = task.get("output")
        result = {"task_id": task_id, "status": status}
        if task.get("failure"): result["failure"] = task.get("failure")
        if status == "SUCCEEDED" and output:
            result["video_url"] = output[0] if isinstance(output, list) else output
        return result
    except Exception as e: raise HTTPException(502, str(e))
