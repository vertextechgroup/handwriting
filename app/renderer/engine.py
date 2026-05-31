import os
import logging
from PIL import Image, ImageChops
from typing import List, Optional

from .text_engine        import TextEngine
from .layout_engine      import LayoutEngine
from .paper_engine       import PaperEngine
from .pen_engine         import PenEngine
from .humanization_engine import HumanizationEngine
from .handwriting_engine  import HandwritingEngine

logger = logging.getLogger(__name__)


class HandwritingRenderer:
    """
    Main orchestrator for the handwriting generation pipeline.

    Defaults are tuned to match Indian school notebook aesthetics:
      - 300 DPI A4
      - Gel pen, dark navy ink
      - Notebook paper (cream, blue rules, red margin)
      - Medium realism intensity
    """

    def __init__(self,
                 dpi:               int   = 300,
                 pen_style:         str   = "gel",
                 ink_color:         str   = "#000080",
                 paper_type:        str   = "notebook",
                 paper_color:       str   = "off_white",
                 realism_intensity: float = 1.2):

        self.paper_type  = paper_type
        self.paper_color = paper_color

        self.layout       = LayoutEngine(dpi=dpi)
        self.paper_engine = PaperEngine(self.layout.width, self.layout.height)
        self.pen          = PenEngine(style=pen_style, color=ink_color)
        self.humanization = HumanizationEngine(intensity=realism_intensity)
        self.hw_engine    = HandwritingEngine(
            self.layout, self.humanization, self.pen
        )

    # ------------------------------------------------------------------
    # Main render method
    # ------------------------------------------------------------------
    def render(self,
               text:              str,
               font_path:         str,
               output_dir:        str,
               font_size:         int = 60,
               progress_callback: Optional[callable] = None) -> List[str]:
        """
        Process `text` and render it into multiple high-quality A4 PNG pages.

        Returns a list of absolute file paths for each saved page.
        """
        os.makedirs(output_dir, exist_ok=True)

        # Load font once to get accurate metrics for text wrapping
        font = self.hw_engine.load_font(font_path, font_size)
        ascent, descent = font.getmetrics()
        line_height     = ascent + descent + 20   # matches HandwritingEngine buffer

        lines_per_page = max(1, int(self.layout.writing_height / line_height))

        text_engine = TextEngine(
            max_width=self.layout.writing_width,
            lines_per_page=lines_per_page,
        )

        def measure_func(s: str) -> float:
            return font.getlength(s)

        # 1. Preprocess: split into pages / lines
        pages_data  = text_engine.preprocess(text, measure_func)
        total_pages = len(pages_data)
        image_paths = []

        logger.info("Rendering %d page(s)…", total_pages)

        for i, page_lines in enumerate(pages_data):
            # 2. Generate paper background
            page_img = self.paper_engine.generate(
                paper_type=self.paper_type,
                color_name=self.paper_color,
            )

            # 3. Render handwriting on a transparent layer
            text_layer = self.hw_engine.render_page(
                page_lines, font_path, font_size=font_size
            )

            # 4. Composite text onto paper using Multiply blend mode for realistic ink staining
            text_bg = Image.new("RGB", page_img.size, (255, 255, 255))
            text_bg.paste(text_layer, (0, 0), text_layer)
            page_img = ImageChops.multiply(page_img, text_bg)

            # 5. Save high-res PNG
            filename = f"page_{i + 1:03d}.png"
            path     = os.path.join(output_dir, filename)
            page_img.save(path, "PNG", dpi=(self.layout.dpi, self.layout.dpi))
            image_paths.append(path)

            logger.info("  Saved page %d/%d → %s", i + 1, total_pages, path)

            if progress_callback:
                progress_callback(i + 1, total_pages)

        return image_paths
