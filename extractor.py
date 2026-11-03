"""Core logic: read metadata, score privacy exposure, and strip metadata."""
import hashlib
import io
import os

from docx import Document
from PIL import Image
from PIL.ExifTags import GPSTAGS, TAGS
from pypdf import PdfReader, PdfWriter

SUPPORTED = {".jpg": "image", ".jpeg": "image", ".png": "image",
             ".pdf": "pdf", ".docx": "docx"}

# (field name, label, severity, points, advice)
RULES = [
    ("GPS", "Exact location", "high", 45, "Anyone with this file can see where it was created."),
    ("BodySerialNumber", "Camera serial number", "high", 25, "Can link photos to one specific camera."),
    ("Author", "Author name", "medium", 15, "Your name is stored inside the file."),
    ("Last Modified By", "Editor name", "medium", 15, "The last person to edit the file is named."),
    ("Artist", "Photographer name", "medium", 15, "Your name is stored inside the photo."),
    ("Model", "Device model", "medium", 10, "Shows which phone or camera you use."),
    ("DateTimeOriginal", "Time taken", "low", 10, "Reveals exactly when the photo was taken."),
    ("Software", "Software used", "low", 5, "Shows which app or version created the file."),
    ("Creator", "Creating application", "low", 5, "Shows which app created the document."),
    ("Producer", "PDF producer", "low", 5, "Shows which tool produced the PDF."),
    ("CreationDate", "Creation date", "low", 5, "Shows when the document was made."),
]


def _hashes(data):
    return {"MD5": hashlib.md5(data).hexdigest(),
            "SHA-256": hashlib.sha256(data).hexdigest()}


def _deg(value):
    d, m, s = (float(x) for x in value)
    return d + m / 60 + s / 3600


def _gps(raw):
    g = {GPSTAGS.get(k, k): v for k, v in raw.items()}
    try:
        lat, lon = _deg(g["GPSLatitude"]), _deg(g["GPSLongitude"])
    except (KeyError, TypeError, ValueError, ZeroDivisionError):
        return None
    if g.get("GPSLatitudeRef") == "S":
        lat = -lat
    if g.get("GPSLongitudeRef") == "W":
        lon = -lon
    return lat, lon


def _image(data, out):
    d = out["details"]
    with Image.open(io.BytesIO(data)) as img:
        d["Format"] = img.format
        d["Dimensions"] = f"{img.width} x {img.height}"
        d["Color mode"] = img.mode
        exif = img.getexif()
        merged = dict(exif)
        try:
            merged.update(exif.get_ifd(0x8769))
        except Exception:
            pass
        for tag_id, value in merged.items():
            name = TAGS.get(tag_id, tag_id)
            if isinstance(value, bytes) or name in ("ExifOffset", "GPSInfo"):
                continue
            d[str(name)] = str(value)
        coords = _gps(exif.get_ifd(0x8825)) if exif else None
        if coords:
            out["gps"] = coords
            d["GPS"] = f"{coords[0]:.5f}, {coords[1]:.5f}"


def _pdf(data, out):
    reader = PdfReader(io.BytesIO(data))
    out["details"]["Pages"] = len(reader.pages)
    out["details"]["Encrypted"] = reader.is_encrypted
    for key, value in (reader.metadata or {}).items():
        out["details"][key.lstrip("/")] = str(value)


def _docx(data, out):
    p = Document(io.BytesIO(data)).core_properties
    fields = {"Title": p.title, "Subject": p.subject, "Author": p.author,
              "Last Modified By": p.last_modified_by, "Keywords": p.keywords,
              "Comments": p.comments, "Created": p.created,
              "Modified": p.modified, "Revision": p.revision}
    for k, v in fields.items():
        if v not in (None, ""):
            out["details"][k] = str(v)


def extract(data, name):
    """Return a dict describing the file. `data` is the file's bytes."""
    kind = SUPPORTED.get(os.path.splitext(name)[1].lower())
    out = {"name": name, "kind": kind, "size_kb": round(len(data) / 1024, 1),
           "hashes": _hashes(data), "details": {}, "gps": None, "error": None}
    if not kind:
        out["error"] = "This file type is not supported yet."
        return out
    try:
        {"image": _image, "pdf": _pdf, "docx": _docx}[kind](data, out)
    except Exception as e:
        out["error"] = f"Could not read this file: {e}"
    return out


def privacy_report(result):
    """Score how much personal information the file exposes (0-100)."""
    present = {k.lower(): v for k, v in result["details"].items()}
    findings, score = [], 0
    for key, label, severity, points, advice in RULES:
        value = present.get(key.lower())
        if value not in (None, "", "None"):
            findings.append({"Field": label, "Found": str(value)[:80],
                             "Risk": severity, "Why it matters": advice})
            score += points
    score = min(score, 100)
    level = "High" if score >= 50 else "Medium" if score >= 20 else "Low"
    return {"score": score, "level": level, "findings": findings}


def clean_file(data, name):
    """Return (bytes, mime) of a copy with personal metadata removed."""
    ext = os.path.splitext(name)[1].lower()
    buf = io.BytesIO()
    if ext in (".jpg", ".jpeg", ".png"):
        with Image.open(io.BytesIO(data)) as img:
            fmt = "PNG" if ext == ".png" else "JPEG"
            img = img.convert("RGB") if fmt == "JPEG" and img.mode != "RGB" else img
            img.save(buf, format=fmt)  # saved without EXIF
        return buf.getvalue(), f"image/{fmt.lower()}"
    if ext == ".pdf":
        reader = PdfReader(io.BytesIO(data))
        writer = PdfWriter()
        for page in reader.pages:
            writer.add_page(page)
        writer.add_metadata({"/Producer": "", "/Creator": "", "/Author": "", "/Title": ""})
        writer.write(buf)
        return buf.getvalue(), "application/pdf"
    if ext == ".docx":
        doc = Document(io.BytesIO(data))
        p = doc.core_properties
        for attr in ("author", "last_modified_by", "title", "subject",
                     "keywords", "comments", "category"):
            setattr(p, attr, "")
        doc.save(buf)
        return buf.getvalue(), ("application/vnd.openxmlformats-officedocument"
                                ".wordprocessingml.document")
    raise ValueError("Unsupported file type")