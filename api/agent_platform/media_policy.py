"""Strict reviewed media operations; no provider URLs or model IDs from agents."""
from __future__ import annotations
import base64
import os
import re

OPERATIONS={
    "vision":("/chat/completions","DRAGONZPYDER_AGENT_VISION_MODEL"),
    "image":("/images","DRAGONZPYDER_AGENT_IMAGE_MODEL"),
    "transcribe":("/audio/transcriptions","DRAGONZPYDER_AGENT_TRANSCRIPTION_MODEL"),
    "speech":("/audio/speech","DRAGONZPYDER_AGENT_SPEECH_MODEL"),
}
AUDIO_FORMATS={"audio/wav":"wav","audio/x-wav":"wav","audio/mpeg":"mp3",
               "audio/mp4":"m4a","audio/webm":"webm","audio/ogg":"ogg","audio/flac":"flac"}
MAX_INPUT_BYTES=3*1024*1024
MAX_OUTPUT_BYTES=5*1024*1024

def configured_operations():
    result={}
    for kind,(path,env) in OPERATIONS.items():
        model=os.getenv(env,"").strip()
        if re.fullmatch(r"[A-Za-z0-9_.:/-]{3,120}",model):
            result[kind]=(path,model)
    return result

def image_mime(raw):
    if raw.startswith(b"\x89PNG\r\n\x1a\n"): return "image/png"
    if raw.startswith(b"\xff\xd8\xff"): return "image/jpeg"
    if raw[:4]==b"RIFF" and raw[8:12]==b"WEBP": return "image/webp"
    raise ValueError("Unsupported inline image")

def audio_matches(raw,fmt):
    return bool({"wav":raw[:4]==b"RIFF" and raw[8:12]==b"WAVE",
        "mp3":raw.startswith(b"ID3") or (len(raw)>2 and raw[0]==255 and raw[1]&224==224),
        "m4a":raw[4:8]==b"ftyp","webm":raw.startswith(b"\x1a\x45\xdf\xa3"),
        "ogg":raw.startswith(b"OggS"),"flac":raw.startswith(b"fLaC")}.get(fmt))

def decode_inline(data,maximum=MAX_INPUT_BYTES):
    if not isinstance(data,str) or len(data)>4*((maximum+2)//3):
        raise ValueError("Media bytes exceed bound")
    raw=base64.b64decode(data,validate=True)
    if not 16<=len(raw)<=maximum:
        raise ValueError("Invalid media byte length")
    return raw

def bounded_text(value,maximum):
    if not isinstance(value,str) or not 1<=len(value.strip())<=maximum:
        raise ValueError("Invalid media text")
    return value

def validate_media_payload(path,body):
    operations=configured_operations()
    kind=next((k for k,(p,m) in operations.items() if p==path and m==body.get("model")),None)
    if not kind: raise ValueError("Media model or modality not approved")
    model=operations[kind][1]
    if kind=="vision":
        if set(body)!={"model","messages","max_tokens"} or body["max_tokens"]!=768:
            raise ValueError("Invalid vision request")
        messages=body["messages"]
        if not isinstance(messages,list) or len(messages)!=1 or set(messages[0])!={"role","content"} or messages[0]["role"]!="user":
            raise ValueError("Invalid vision input")
        parts=messages[0]["content"]
        if not isinstance(parts,list) or len(parts)!=2 or parts[0].get("type")!="text" or parts[1].get("type")!="image_url":
            raise ValueError("Vision requires one selected image")
        if set(parts[0])!={"type","text"} or set(parts[1])!={"type","image_url"} or set(parts[1]["image_url"])!={"url"}:
            raise ValueError("Invalid vision part")
        bounded_text(parts[0]["text"],2000)
        url=parts[1]["image_url"]["url"]
        if not isinstance(url,str) or not url.startswith("data:") or ";base64," not in url:
            raise ValueError("Only inline selected images are allowed")
        mime,encoded=url[5:].split(";base64,",1)
        if image_mime(decode_inline(encoded))!=mime:
            raise ValueError("Image header mismatch")
    elif kind=="image":
        if set(body)!={"model","prompt","n"} or type(body["n"]) is not int or body["n"]!=1:
            raise ValueError("Exactly one image per invocation")
        bounded_text(body["prompt"],1600)
    elif kind=="transcribe":
        if set(body)!={"model","input_audio"} or set(body["input_audio"])!={"data","format"}:
            raise ValueError("Invalid transcription request")
        audio=body["input_audio"]
        if not audio_matches(decode_inline(audio["data"]),audio["format"]):
            raise ValueError("Audio header mismatch")
    else:
        if set(body)-{"model","input","response_format","voice"} or body.get("response_format")!="mp3":
            raise ValueError("Unsupported speech format")
        bounded_text(body.get("input"),1200)
        if "voice" in body and (not model.startswith("openai/") or body["voice"]!="alloy"):
            raise ValueError("Unsupported speech voice")
    return kind
