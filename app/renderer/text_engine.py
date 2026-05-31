import re
from typing import List, Callable, Dict, Any


class TextEngine:
    """
    Handles text preprocessing, smart wrapping, and human-like formatting.

    Detects:
      - Markdown headings (#, ##)
      - ALL-CAPS headings
      - Dash-prefixed bullet lists  (- item, * item)
      - Numbered lists              (1. item, 2) item)
      - Leading indentation
    """

    # Bullet prefix patterns
    _BULLET_RE  = re.compile(r"^(\s*)([-*•])\s+(.*)$")
    _NUMBER_RE  = re.compile(r"^(\s*)(\d+[.):])\s+(.*)$")
    _HEADING_RE = re.compile(r"^(#{1,3})\s+(.*)")

    def __init__(self, max_width: int = 2000, lines_per_page: int = 35):
        self.max_width     = max_width
        self.lines_per_page = lines_per_page

    # ------------------------------------------------------------------
    # Main entry-point
    # ------------------------------------------------------------------
    def preprocess(self,
                   text: str,
                   measure_func: Callable[[str], float]
                   ) -> List[List[Dict[str, Any]]]:
        """
        Split text into pages of lines.

        Each line dict:
          {
            "text":       str,
            "is_heading": bool,
            "is_bullet":  bool,   # True for - / * / • / numbered items
            "bullet_prefix": str, # e.g. "-", "1.", "a)" — empty string if not bullet
            "indent":     int,    # pixel indent (0 for plain body text)
          }
        """
        text = text.replace("\r\n", "\n")
        raw_lines = text.split("\n")

        pages: List[List[Dict]] = []
        current_page: List[Dict] = []

        for raw in raw_lines:
            # Blank line → preserve as empty spacer
            if not raw.strip():
                if current_page:
                    current_page.append(self._blank_line())
                continue

            meta = self._classify_line(raw)
            wrapped = self._wrap_paragraph(
                meta["text"], measure_func, meta["indent"]
            )

            for i, w_line in enumerate(wrapped):
                if len(current_page) >= self.lines_per_page:
                    pages.append(current_page)
                    current_page = []

                # Only the first wrapped sub-line carries heading/bullet marker
                is_first = (i == 0)
                current_page.append({
                    "text":          w_line,
                    "is_heading":    meta["is_heading"] and is_first,
                    "is_bullet":     meta["is_bullet"]  and is_first,
                    "bullet_prefix": meta["bullet_prefix"] if is_first else "",
                    "indent":        meta["indent"],
                })

        if current_page:
            pages.append(current_page)

        return pages

    # ------------------------------------------------------------------
    # Line classification
    # ------------------------------------------------------------------
    def _classify_line(self, line: str) -> Dict[str, Any]:
        """Return metadata dict for one raw input line."""
        is_heading     = False
        is_bullet      = False
        bullet_prefix  = ""
        indent_px      = 0
        clean          = line

        # --- Heading: Markdown style ---
        m = self._HEADING_RE.match(line.strip())
        if m:
            is_heading = True
            clean = m.group(2).strip()
            return self._meta(clean, is_heading, is_bullet, bullet_prefix, 0)

        # --- Heading: ALL CAPS (≥4 chars, not all punctuation) ---
        stripped = line.strip()
        if (stripped.isupper()
                and len(stripped) > 3
                and not re.match(r"^[\W\d]+$", stripped)):
            is_heading = True
            clean = stripped
            return self._meta(clean, is_heading, is_bullet, bullet_prefix, 0)

        # --- Bullet list: dash / star / dot ---
        m = self._BULLET_RE.match(line)
        if m:
            leading_spaces = len(m.group(1))
            bullet_prefix  = m.group(2)          # "-", "*", "•"
            clean          = m.group(3).strip()
            is_bullet      = True
            # Indent body by 40px per level
            indent_px      = max(0, leading_spaces) * 12 + 40
            return self._meta(clean, is_heading, is_bullet, bullet_prefix, indent_px)

        # --- Numbered list ---
        m = self._NUMBER_RE.match(line)
        if m:
            leading_spaces = len(m.group(1))
            bullet_prefix  = m.group(2)          # "1.", "2)", etc.
            clean          = m.group(3).strip()
            is_bullet      = True
            indent_px      = max(0, leading_spaces) * 12 + 40
            return self._meta(clean, is_heading, is_bullet, bullet_prefix, indent_px)

        # --- Plain body text ---
        # Honour leading whitespace as indentation
        m_indent = re.match(r"^(\s+)", line)
        if m_indent:
            indent_px = len(m_indent.group(1)) * 14
        clean = line.strip()

        return self._meta(clean, is_heading, is_bullet, bullet_prefix, indent_px)

    @staticmethod
    def _meta(text, is_heading, is_bullet, bullet_prefix, indent) -> Dict[str, Any]:
        return {
            "text":          text,
            "is_heading":    is_heading,
            "is_bullet":     is_bullet,
            "bullet_prefix": bullet_prefix,
            "indent":        indent,
        }

    @staticmethod
    def _blank_line() -> Dict[str, Any]:
        return {
            "text": "", "is_heading": False,
            "is_bullet": False, "bullet_prefix": "", "indent": 0,
        }

    # ------------------------------------------------------------------
    # Word-wrap
    # ------------------------------------------------------------------
    def _wrap_paragraph(self,
                        paragraph: str,
                        measure_func: Callable[[str], float],
                        indent: int) -> List[str]:
        """Wrap a paragraph into lines that fit within max_width − indent."""
        if not paragraph:
            return [""]

        effective_width = self.max_width - indent
        words   = paragraph.split()
        lines   = []
        current = []

        for word in words:
            test = " ".join(current + [word])
            if measure_func(test) > effective_width:
                if not current:
                    lines.append(word)   # single very-long word — keep as-is
                else:
                    lines.append(" ".join(current))
                    current = [word]
            else:
                current.append(word)

        if current:
            lines.append(" ".join(current))

        return lines
