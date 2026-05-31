import re
import logging

logger = logging.getLogger(__name__)

DEFAULT_CHARS_PER_PAGE = 1200
MAX_CHARS_PER_PAGE = 1500

def split_text_into_pages(
    text: str,
    chars_per_page: int = DEFAULT_CHARS_PER_PAGE,
    max_chars: int = MAX_CHARS_PER_PAGE,
) -> list[str]:
    """
    Split text into pages while respecting sentence and paragraph boundaries.
    """
    if not text or not text.strip():
        return []

    # Normalize whitespace
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"\n{3,}", "\n\n", text)

    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    pages = []
    current_page = ""

    for para in paragraphs:
        # If paragraph itself is too long, split it by sentences
        if len(para) > max_chars:
            sentences = _split_into_sentences(para)
            for sentence in sentences:
                if len(current_page) + len(sentence) + 2 <= max_chars:
                    current_page += (" " if current_page else "") + sentence
                else:
                    if current_page:
                        pages.append(current_page.strip())
                    current_page = sentence
        else:
            # Check if adding this paragraph exceeds limit
            candidate = (current_page + "\n\n" + para).strip() if current_page else para
            if len(candidate) <= max_chars:
                current_page = candidate
            else:
                if current_page:
                    pages.append(current_page.strip())
                current_page = para

    if current_page.strip():
        pages.append(current_page.strip())

    return pages

def _split_into_sentences(text: str) -> list[str]:
    # Basic sentence splitter
    sentence_endings = re.compile(r'(?<=[.!?])\s+')
    return [s.strip() for s in sentence_endings.split(text) if s.strip()]

def get_page_stats(pages: list[str]) -> dict:
    if not pages:
        return {"page_count": 0, "total_chars": 0, "avg_chars_per_page": 0}
    total = sum(len(p) for p in pages)
    return {
        "page_count": len(pages),
        "total_chars": total,
        "avg_chars_per_page": total // len(pages),
    }
