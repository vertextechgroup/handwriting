import os
import logging
import zipfile
from typing import List

logger = logging.getLogger(__name__)

from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from PIL import Image

logger = logging.getLogger(__name__)

def build_pdf(image_paths: List[str], output_path: str) -> str:
    """Combine images into a single A4 PDF with high resolution preservation."""
    if not image_paths:
        raise ValueError("No images provided for PDF generation.")

    valid_paths = [p for p in image_paths if os.path.isfile(p)]
    if not valid_paths:
        raise ValueError("No valid image files found for PDF generation.")

    try:
        # A4 size in points (72 DPI)
        w_pt, h_pt = A4
        c = canvas.Canvas(output_path, pagesize=A4)
        
        for img_path in valid_paths:
            # ReportLab's drawImage can take dimensions in points.
            # It will scale the image to fit these dimensions.
            # Since our images are high-res (e.g. 2480x3508 for 300 DPI),
            # placing them on a 595x841 pt page will effectively embed them at high DPI.
            c.drawImage(img_path, 0, 0, width=w_pt, height=h_pt, preserveAspectRatio=True, anchor='c')
            c.showPage()
        
        c.save()
        return output_path
    except Exception as e:
        logger.error(f"Failed to build PDF with ReportLab: {e}")
        # Fallback to a simpler method if needed, but ReportLab is preferred
        raise


def build_zip(image_paths: List[str], output_path: str) -> str:
    """Create a ZIP archive of the images."""
    with zipfile.ZipFile(output_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for img_path in image_paths:
            if os.path.isfile(img_path):
                zf.write(img_path, arcname=os.path.basename(img_path))
    return output_path
