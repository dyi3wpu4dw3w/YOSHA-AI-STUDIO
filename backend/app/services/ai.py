import os
from pathlib import Path
from openai import OpenAI

def client():
    key = os.getenv("OPENAI_API_KEY", "").strip()
    if not key:
        raise RuntimeError("OPENAI_API_KEY is not configured. Add it to the server .env file.")
    return OpenAI(api_key=key)

def generate_script(prompt: str, language: str = "Arabic", style: str = "cinematic"):
    c = client()
    model = os.getenv("OPENAI_TEXT_MODEL", "gpt-4o-mini")
    response = c.chat.completions.create(model=model, messages=[
        {"role": "system", "content": f"You are an expert film writer and creative director. Write in {language}. Style: {style}. Return a production-ready script with title, logline, scene headings, visual direction, dialogue and narration. Be original."},
        {"role": "user", "content": prompt},
    ], temperature=0.8)
    return response.choices[0].message.content or ""

def generate_image(prompt: str, output_path: Path):
    import base64
    result = client().images.generate(model=os.getenv("OPENAI_IMAGE_MODEL", "gpt-image-1"), prompt=prompt, size="1024x1024")
    b64 = getattr(result.data[0], "b64_json", None)
    if not b64:
        raise RuntimeError("Image provider did not return image bytes.")
    output_path.write_bytes(base64.b64decode(b64))
    return output_path

def generate_speech(text: str, output_path: Path, voice: str = "alloy"):
    with client().audio.speech.with_streaming_response.create(model=os.getenv("OPENAI_TTS_MODEL", "gpt-4o-mini-tts"), voice=voice, input=text) as response:
        response.stream_to_file(output_path)
    return output_path

def transcribe(audio_path: Path):
    with audio_path.open("rb") as f:
        result = client().audio.transcriptions.create(model=os.getenv("OPENAI_STT_MODEL", "whisper-1"), file=f, response_format="verbose_json")
    segments = [{"start": float(item.start), "end": float(item.end), "text": item.text.strip()} for item in (getattr(result, "segments", None) or [])]
    return {"text": result.text, "segments": segments}
