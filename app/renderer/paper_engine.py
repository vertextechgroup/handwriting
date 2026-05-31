import random
import math
from PIL import Image, ImageDraw, ImageFilter, ImageOps, ImageChops
from typing import Tuple


class PaperEngine:
    """
    Generates realistic paper backgrounds that match classic Indian school
    notebook aesthetics:
      - Off-white / cream paper with subtle grain
      - Thin light-blue horizontal ruled lines
      - A single red vertical margin line (~1/6 from left)
      - Optional header box for exam paper
    """

    PAPER_COLORS = {
        "white":           (255, 255, 255),
        "off_white":       (253, 252, 248),
        "cream":           (254, 252, 242),
        "yellow_notebook": (255, 253, 208),
    }

    def __init__(self, width: int, height: int):
        self.width = width
        self.height = height

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def generate(self, paper_type: str = "notebook",
                 color_name: str = "off_white") -> Image.Image:
        """Return a fully rendered paper background image (RGB)."""
        color = self.PAPER_COLORS.get(color_name, self.PAPER_COLORS["off_white"])
        paper = Image.new("RGB", (self.width, self.height), color=color)

        paper = self._add_texture(paper)

        if paper_type in ("ruled", "notebook", "exam"):
            margin = paper_type in ("notebook", "exam")
            header = paper_type == "exam"
            paper = self._draw_ruled_lines(paper,
                                           margin_line=margin,
                                           header_box=header)
        
        paper = self._add_lighting(paper)
        return paper

    # ------------------------------------------------------------------
    # Texture & Lighting
    # ------------------------------------------------------------------
    def _add_texture(self, image: Image.Image) -> Image.Image:
        """Add very subtle paper grain so the background isn't pure flat."""
        w, h = image.size
        # Downsample → add noise → upsample (cheap but effective grain)
        noise = Image.new("L", (w // 6, h // 6))
        noise_data = bytes([random.randint(242, 255)
                            for _ in range((w // 6) * (h // 6))])
        noise.frombytes(noise_data)
        noise = noise.resize((w, h), resample=Image.BILINEAR)
        noise = noise.filter(ImageFilter.GaussianBlur(radius=1.5))

        noise_rgb = ImageOps.colorize(noise,
                                      black=(228, 222, 210),
                                      white=(255, 255, 255))
        return Image.blend(image, noise_rgb, 0.18)

    def _add_lighting(self, image: Image.Image) -> Image.Image:
        """Add subtle organic lighting variation to make the paper look real."""
        w, h = image.size
        # Create a large-scale slow noise/gradient for lighting
        light = Image.new("L", (w // 20, h // 20))
        l_data = bytes([random.randint(240, 255) for _ in range((w // 20) * (h // 20))])
        light.frombytes(l_data)
        light = light.resize((w, h), resample=Image.BICUBIC)
        light = light.filter(ImageFilter.GaussianBlur(radius=50))
        
        return ImageChops.multiply(image, light.convert("RGB"))

    # ------------------------------------------------------------------
    # Ruled lines
    # ------------------------------------------------------------------
    def _draw_ruled_lines(self,
                          image: Image.Image,
                          line_spacing: int = 80,
                          margin_line: bool = True,
                          header_box: bool = False) -> Image.Image:
        """
        Draw horizontal blue ruled lines and (optionally) a red margin line.

        The line_spacing default (80px) is at 300 DPI and matches what
        LayoutEngine / HandwritingEngine use, so text sits neatly between lines.
        """
        draw = ImageDraw.Draw(image, "RGBA")

        # ---- Horizontal ruled lines ----
        # Light blue, similar to real notebook lines: ~(176, 200, 220)
        ruled_color = (176, 200, 224)
        ruled_alpha = 210          # slightly transparent

        start_y = 380              # leave a top margin for the title / date area
        y = start_y
        while y < self.height - 160:
            self._draw_faint_line(
                draw,
                start=(0, y), end=(self.width, y),
                color=ruled_color + (ruled_alpha,),
                width=2,
                jitter=0.5
            )
            y += line_spacing

        # ---- Red vertical margin line ----
        if margin_line:
            # Approximately 1/6 of page width — classic Indian notebook
            margin_x = self.width // 6
            self._draw_faint_line(
                draw,
                start=(margin_x, 0), end=(margin_x, self.height),
                color=(210, 60, 60, 190),
                width=3,
                jitter=0.6
            )

        # ---- Header box for exam paper ----
        if header_box:
            box_h = 280
            draw.rectangle(
                [(self.width // 6 + 10, 40),
                 (self.width - 60, 40 + box_h)],
                outline=(170, 185, 210, 200),
                width=3
            )
            # A horizontal divider one third down
            div_y = 40 + box_h // 3
            draw.line(
                [(self.width // 6 + 10, div_y),
                 (self.width - 60, div_y)],
                fill=(170, 185, 210, 160),
                width=2
            )

        return image

    # ------------------------------------------------------------------
    # Internal: slightly wobbly line (simulates pencil / cheap ballpoint)
    # ------------------------------------------------------------------
    def _draw_faint_line(self,
                         draw: ImageDraw.Draw,
                         start: Tuple[int, int],
                         end: Tuple[int, int],
                         color: Tuple,
                         width: int = 2,
                         jitter: float = 0.4,
                         steps: int = 60) -> None:
        """Draw a line that has a tiny amount of positional jitter and variable thickness."""
        x1, y1 = start
        x2, y2 = end
        pts = []
        for i in range(steps + 1):
            t = i / steps
            # Add a slow organic wobble using sine waves + jitter
            wobble = math.sin(t * 12) * 0.8
            px = x1 + (x2 - x1) * t + random.gauss(0, jitter) + wobble
            py = y1 + (y2 - y1) * t + random.gauss(0, jitter) + wobble
            pts.append((px, py))

        for i in range(len(pts) - 1):
            # Variable thickness for more realism
            current_width = width if random.random() > 0.1 else width + 1
            draw.line([pts[i], pts[i + 1]], fill=color, width=current_width)
