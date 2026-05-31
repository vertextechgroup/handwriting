import os
import re
import logging
from werkzeug.utils import secure_filename as wz_secure
from PIL import Image

logger = logging.getLogger(__name__)

ALLOWED_EXTENSIONS = {"pdf", "docx", "txt"}

def is_allowed_file(filename: str) -> bool:
    """Check if the file extension is allowed."""
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

def secure_filename(filename: str) -> str:
    """Sanitize filename to prevent path traversal."""
    name = wz_secure(filename)
    if not name:
        name = "unnamed_file"
    return name

def generate_thumbnail(image_path: str, output_dir: str, size=(300, 300)) -> str:
    """Generate a thumbnail for a given image."""
    try:
        img = Image.open(image_path)
        img.thumbnail(size)
        
        base_name = os.path.basename(image_path)
        thumb_name = f"thumb_{base_name}"
        thumb_path = os.path.join(output_dir, thumb_name)
        
        img.save(thumb_path, "PNG")
        return thumb_path
    except Exception as e:
        logger.error(f"Failed to generate thumbnail for {image_path}: {e}")
        return ""
