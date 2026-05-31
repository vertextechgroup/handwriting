import os
import logging
from typing import Optional

logger = logging.getLogger(__name__)

def extract_text(file_path: str) -> str:
    """Auto-detect file type and extract text."""
    ext = os.path.splitext(file_path)[1].lower()
    
    if ext == ".docx":
        return _extract_from_docx(file_path)
    elif ext == ".pdf":
        return _extract_from_pdf(file_path)
    elif ext == ".txt":
        return _extract_from_txt(file_path)
    else:
        raise ValueError(f"Unsupported file type: {ext}")

def _extract_from_docx(file_path: str) -> str:
    from docx import Document
    doc = Document(file_path)
    paragraphs = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
    return "\n\n".join(paragraphs)

def _extract_from_pdf(file_path: str) -> str:
    import PyPDF2
    text_parts = []
    with open(file_path, "rb") as f:
        reader = PyPDF2.PdfReader(f)
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                text_parts.append(page_text.strip())
    return "\n\n".join(text_parts)

def _extract_from_txt(file_path: str) -> str:
    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
        return f.read().strip()
