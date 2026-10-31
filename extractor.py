import os
from datetime import datetime
from PIL import Image
from PIL.ExifTags import TAGS, GPSTAGS
from pypdf import PdfReader
from docx import Document


def basic_info(path):
    """Details every file has, whatever its type."""
    stat = os.stat(path)
    return {
        "File Name": os.path.basename(path),
        "Size (KB)": round(stat.st_size / 1024, 2),
        "Created": datetime.fromtimestamp(stat.st_ctime).strftime("%Y-%m-%d %H:%M:%S"),
        "Modified": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
    }


def _to_degrees(value):
    """Convert GPS (degrees, minutes, seconds) to decimal degrees."""
    d, m, s = [float(x) for x in value]
    return d + (m / 60.0) + (s / 3600.0)


def _gps_location(exif):
    """Return a Google Maps link if the photo has GPS data."""
    gps_ifd = exif.get_ifd(0x8825)
    if not gps_ifd:
        return None
    gps = {GPSTAGS.get(k, k): v for k, v in gps_ifd.items()}
    try:
        lat = _to_degrees(gps["GPSLatitude"])
        lon = _to_degrees(gps["GPSLongitude"])
        if gps.get("GPSLatitudeRef") == "S":
            lat = -lat
        if gps.get("GPSLongitudeRef") == "W":
            lon = -lon
        return f"https://www.google.com/maps?q={lat:.6f},{lon:.6f}"
    except (KeyError, TypeError, ValueError):
        return None


def image_metadata(path):
    data = {}
    with Image.open(path) as img:
        data["Format"] = img.format
        data["Dimensions"] = f"{img.width} x {img.height}"
        data["Color Mode"] = img.mode
        exif = img.getexif()
        for tag_id, value in exif.items():
            tag = TAGS.get(tag_id, tag_id)
            if isinstance(value, bytes):
                continue  # skip raw binary data
            data[str(tag)] = str(value)
        location = _gps_location(exif)
        if location:
            data["GPS Location"] = location
    return data


def pdf_metadata(path):
    reader = PdfReader(path)
    data = {"Pages": len(reader.pages), "Encrypted": reader.is_encrypted}
    if reader.metadata:
        for key, value in reader.metadata.items():
            data[key.lstrip("/")] = str(value)
    return data


def docx_metadata(path):
    p = Document(path).core_properties
    return {
        "Title": p.title,
        "Author": p.author,
        "Last Modified By": p.last_modified_by,
        "Created": str(p.created),
        "Modified": str(p.modified),
        "Revision": p.revision,
    }


HANDLERS = {
    ".jpg": image_metadata,
    ".jpeg": image_metadata,
    ".png": image_metadata,
    ".pdf": pdf_metadata,
    ".docx": docx_metadata,
}


def extract(path):
    """Main function: takes a file path, returns a dictionary of metadata."""
    if not os.path.isfile(path):
        return {"Error": "File not found"}

    result = basic_info(path)
    ext = os.path.splitext(path)[1].lower()
    handler = HANDLERS.get(ext)

    if handler is None:
        result["Note"] = f"File type '{ext}' is not supported yet"
        return result

    try:
        result.update(handler(path))
    except Exception as e:
        result["Error"] = f"Could not read metadata: {e}"
    return result