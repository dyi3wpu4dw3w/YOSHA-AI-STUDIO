import os, uuid, shutil, subprocess, json
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, PlainTextResponse
from pydantic import BaseModel
from sqlmodel import SQLModel, Field, Session, create_engine, select
from .services.ai import generate_script, generate_image, generate_speech, transcribe
from .services.video import create_clip, get_clip, download_clip, split_duration

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
    duration: int = 60
    ratio: str = "16:9"
class VideoJob(SQLModel, table=True):
    id: str = Field(primary_key=True)
    prompt: str
    duration: int
    ratio: str
    segment_tasks: str = "[]"
    status: str = "submitted"
    output_url: str = ""
    error: str = ""
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
SQLModel.metadata.create_all(engine)
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
    if len(data.prompt) > 7000: raise HTTPException(400, "Prompt must be 7000 characters or fewer")
    try: durations = split_duration(data.duration)
    except ValueError as e: raise HTTPException(400, str(e))
    if data.ratio not in ("16:9", "9:16", "1:1", "21:9", "4:3", "3:4"): raise HTTPException(400, "Unsupported aspect ratio")
    job_id = uuid.uuid4().hex
    task_rows = []
    try:
        for index, seconds in enumerate(durations):
            continuity = (
                f"\n\nThis is continuous long-form film segment {index + 1} of {len(durations)}, lasting {seconds} seconds. "
                "Keep the same characters, wardrobe, locations, visual style, lighting logic and cinematic language throughout the whole film. "
                + ("Establish the story and characters." if index == 0 else "Continue the same story naturally from the preceding segment; do not restart or introduce unrelated characters.")
                + (" Bring the story to a satisfying conclusion." if index == len(durations)-1 else " End with a visual action that can flow naturally into the next segment.")
            )
            task = await create_clip(data.prompt.strip() + continuity, seconds, data.ratio)
            task_rows.append({"id": task["id"], "duration": seconds, "status": task.get("status", "submitted")})
        with Session(engine) as s:
            s.add(VideoJob(id=job_id, prompt=data.prompt.strip(), duration=data.duration, ratio=data.ratio, segment_tasks=json.dumps(task_rows)))
            s.commit()
        return {"job_id": job_id, "status": "submitted", "segments": len(task_rows), "segment_durations": durations}
    except Exception as e:
        raise HTTPException(502, str(e))

@app.get("/api/ai/video/{job_id}")
async def ai_video_status(job_id: str):
    with Session(engine) as s: job = s.get(VideoJob, job_id)
    if not job: raise HTTPException(404, "Video job not found")
    if job.output_url:
        return {"job_id": job_id, "status": "succeeded", "video_url": job.output_url, "duration": job.duration}
    if job.error:
        return {"job_id": job_id, "status": "failed", "error": job.error}
    rows = json.loads(job.segment_tasks)
    try:
        for row in rows:
            task = await get_clip(row["id"])
            row["status"] = task.get("status", "unknown")
            if row["status"] == "failed":
                message = task.get("message") or task.get("error") or "Kling clip generation failed"
                with Session(engine) as s:
                    current=s.get(VideoJob,job_id); current.error=str(message); current.status="failed"; current.segment_tasks=json.dumps(rows); s.add(current); s.commit()
                return {"job_id":job_id,"status":"failed","error":str(message),"segments":rows}
            outputs = task.get("outputs") or []
            if row["status"] == "succeeded" and outputs:
                row["url"] = outputs[0].get("url")
        with Session(engine) as s:
            current=s.get(VideoJob,job_id); current.segment_tasks=json.dumps(rows); current.status="processing"; s.add(current); s.commit()
        if not all(row["status"] == "succeeded" and row.get("url") for row in rows):
            return {"job_id":job_id,"status":"processing","segments":rows,"completed_segments":sum(1 for x in rows if x["status"]=="succeeded"),"total_segments":len(rows)}
        local_files=[]
        for i,row in enumerate(rows):
            path=OUTPUTS/f"kling-{job_id}-{i:02}.mp4"
            await download_clip(row["url"], str(path)); local_files.append(path)
        manifest=OUTPUTS/f"kling-{job_id}.txt"
        manifest.write_text("".join(f"file '{p.as_posix()}'\n" for p in local_files),encoding="utf-8")
        final=OUTPUTS/f"kling-film-{job_id}.mp4"
        proc=subprocess.run(["ffmpeg","-y","-f","concat","-safe","0","-i",str(manifest),"-c:v","libx264","-preset","veryfast","-crf","20","-c:a","aac","-movflags","+faststart",str(final)],capture_output=True)
        manifest.unlink(missing_ok=True)
        for p in local_files: p.unlink(missing_ok=True)
        if proc.returncode: raise RuntimeError(proc.stderr.decode(errors="ignore")[-1500:])
        url=f"/outputs/{final.name}"
        with Session(engine) as s:
            current=s.get(VideoJob,job_id); current.output_url=url; current.status="succeeded"; current.segment_tasks=json.dumps(rows); s.add(current); s.commit()
        return {"job_id":job_id,"status":"succeeded","video_url":url,"duration":job.duration,"segments":rows}
    except Exception as e:
        with Session(engine) as s:
            current=s.get(VideoJob,job_id); current.error=str(e); current.status="failed"; s.add(current); s.commit()
        raise HTTPException(502, str(e))
