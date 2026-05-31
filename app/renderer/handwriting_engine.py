import os
import random
import math
from PIL import Image, ImageDraw, ImageFont, ImageFilter

from .layout_engine      import LayoutEngine
from .humanization_engine import HumanizationEngine
from .pen_engine         import PenEngine


class HandwritingEngine:
    """
    Core engine for rendering handwriting glyph-by-glyph with realistic
    human imperfections.

    Key improvements over the original:
      - Line-level slant simulation (hand rises or falls across a line)
      - Bullet prefix drawn separately so indented text aligns cleanly
      - Heading underline is thinner and slightly wobbly (closer to real pen)
      - Pressure variation is per-word, not per-char (more realistic)
      - Per-page humanization reset so each page starts fresh
    """

    def __init__(self,
                 layout:       LayoutEngine,
                 humanization: HumanizationEngine,
                 pen:          PenEngine):
        self.layout       = layout
        self.humanization = humanization
        self.pen          = pen
        self._fonts: dict = {}

    # ------------------------------------------------------------------
    # Font loading with fallbacks
    # ------------------------------------------------------------------
    def load_font(self, font_path: str, size: int = 60) -> ImageFont.FreeTypeFont:
        key = (font_path, size)
        if key not in self._fonts:
            font = self._try_load_font(font_path, size)
            self._fonts[key] = font
        return self._fonts[key]

    @staticmethod
    def _try_load_font(path: str, size: int) -> ImageFont.FreeTypeFont:
        candidates = [path] + [
            "C:\\Windows\\Fonts\\Inkfree.ttf",
            "C:\\Windows\\Fonts\\segoesc.ttf",
            "C:\\Windows\\Fonts\\segoepr.ttf",
            "C:\\Windows\\Fonts\\comic.ttf",
            "C:\\Windows\\Fonts\\arial.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationMono-Regular.ttf",
            "/System/Library/Fonts/Helvetica.ttc",
        ]
        for c in candidates:
            if c and os.path.exists(c):
                try:
                    return ImageFont.truetype(c, size)
                except Exception:
                    continue
        return ImageFont.load_default()

    # ------------------------------------------------------------------
    # Page rendering
    # ------------------------------------------------------------------
    def render_page(self,
                    lines:     list,
                    font_path: str,
                    font_size: int = 60) -> Image.Image:
        """
        Render a list of line-dicts onto a transparent RGBA layer.
        The caller composites this onto the paper background.
        """
        self.humanization.reset_page()
        is_script = "cursive" in font_path.lower() or "script" in font_path.lower()

        text_layer = Image.new(
            "RGBA", (self.layout.width, self.layout.height), (0, 0, 0, 0)
        )
        draw = ImageDraw.Draw(text_layer)

        font      = self.load_font(font_path, font_size)
        ink_rgb   = self.pen.get_color_rgb()
        ascent, descent = font.getmetrics()
        line_height     = ascent + descent
        line_spacing    = line_height + 20   # 20 px buffer (matches PaperEngine)
        total_lines     = len(lines)

        for i, line_data in enumerate(lines):
            if not line_data or not line_data.get("text"):
                continue
            
            self.humanization.update_fatigue(i, total_lines)

            text       = line_data["text"]
            is_heading = line_data.get("is_heading", False)
            is_bullet  = line_data.get("is_bullet",  False)
            prefix     = line_data.get("bullet_prefix", "")
            indent     = line_data.get("indent", 0)

            # --- Base coordinates ---
            x_start, line_top = self.layout.get_line_coordinates(
                i, line_spacing=line_spacing
            )
            # Baseline sits at ascent below the top of the line slot
            baseline_y = line_top + ascent

            # --- Line-level drift (whole-line vertical shift) ---
            baseline_y += int(self.humanization.get_line_drift())

            # --- Slant parameters (hand rising/falling across this line) ---
            slant_per_char = random.gauss(0, 0.03) * self.humanization.intensity

            # --- Draw bullet/number prefix ---
            prefix_width = 0
            if is_bullet and prefix:
                prefix_width = self._render_bullet_prefix(
                    text_layer, draw, font,
                    x=x_start, baseline_y=baseline_y,
                    prefix=prefix, ink_rgb=ink_rgb
                )

            # --- Draw characters ---
            current_x = x_start + indent + prefix_width
            end_x = self._render_line_chars(
                text_layer, font, font_size,
                text=text,
                start_x=current_x,
                baseline_y=baseline_y,
                ink_rgb=ink_rgb,
                slant_per_char=slant_per_char,
                is_script=is_script
            )

            # --- Heading underline ---
            if is_heading:
                ul_y = baseline_y + 12
                self._draw_natural_underline(
                    draw, x_start, end_x, ul_y, ink_rgb
                )

        # Post-process ink effects
        text_layer = self.pen.apply_ink_effect(text_layer)
        return text_layer

    # ------------------------------------------------------------------
    # Render bullet/number prefix
    # ------------------------------------------------------------------
    def _render_bullet_prefix(self,
                               layer:      Image.Image,
                               draw:       ImageDraw.Draw,
                               font,
                               x:          int,
                               baseline_y: int,
                               prefix:     str,
                               ink_rgb:    tuple) -> int:
        """
        Draw the bullet symbol/number to the LEFT of the indent offset.
        Returns the width consumed (so text body knows where to start).
        """
        # Map raw markdown prefix to a drawn symbol
        symbol_map = {"-": "-", "*": "-", "•": "•"}
        symbol = symbol_map.get(prefix, prefix)   # keep "1.", "a)" etc.

        pressure  = self.humanization.get_pressure_variation()
        color     = ink_rgb + (int(255 * pressure),)
        small_font_size = max(30, int(font.size * 0.85))

        # Try to use a slightly smaller size for the dash
        try:
            small_font = ImageFont.truetype(font.path, small_font_size)
        except Exception:
            small_font = font

        sym_w = small_font.getlength(symbol + " ")
        angle = self.humanization.get_char_rotation() * 0.5
        sym_img = Image.new("RGBA", (int(sym_w) + 20, font.size + 20), (0, 0, 0, 0))
        sym_draw = ImageDraw.Draw(sym_img)
        sym_draw.text((10, 10), symbol, font=small_font, fill=color)
        if angle:
            sym_img = sym_img.rotate(angle, resample=Image.BICUBIC, expand=True)

        dx, dy = self.humanization.get_char_offset()
        paste_x = x + int(dx)
        paste_y = baseline_y - small_font.getmetrics()[0] + int(dy)
        layer.paste(sym_img, (paste_x, paste_y), sym_img)

        return int(sym_w) + 10   # gap between prefix and text

    # ------------------------------------------------------------------
    # Render a single line character-by-character
    # ------------------------------------------------------------------
    def _render_line_chars(self,
                            layer:         Image.Image,
                            font,
                            font_size:     int,
                            text:          str,
                            start_x:       float,
                            baseline_y:    float,
                            ink_rgb:       tuple,
                            slant_per_char: float = 0.0,
                            is_script:     bool = False) -> float:
        """
        Draw every character individually, returning the x position at the end
        (used for underline calculation).
        """
        padding  = font_size // 2
        current_x = start_x
        char_count = 0

        # Choose one pressure value and slant per pseudo-word (3-8 chars) for realism
        pressure_interval = random.randint(3, 8)
        current_pressure  = self.humanization.get_pressure_variation()
        word_slant        = self.humanization.get_word_slant()

        for char in text:
            char_count += 1
            if char_count % pressure_interval == 0:
                current_pressure  = self.humanization.get_pressure_variation()
                word_slant        = self.humanization.get_word_slant()
                pressure_interval = random.randint(3, 8)

            if char == " ":
                current_x += font.getlength(" ") + \
                              self.humanization.get_word_spacing_jitter()
                continue

            # Bounding box of the glyph
            try:
                bbox = font.getbbox(char)
            except Exception:
                current_x += font.getlength(char)
                continue

            l, t, r, b = bbox
            w, h = r - l, b - t
            if w <= 0 or h <= 0:
                current_x += font.getlength(char)
                continue

            # --- Random character scaling ---
            scale = self.humanization.get_char_scale()
            if scale != 1.0:
                w, h = int(w * scale), int(h * scale)

            # Draw char onto a padded canvas (avoids clipping on rotation)
            canvas_w = w + padding * 2
            canvas_h = h + padding * 2
            char_img  = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
            char_draw = ImageDraw.Draw(char_img)

            color = ink_rgb + (int(255 * current_pressure),)
            char_draw.text((padding - l, padding - t), char, font=font, fill=color)

            # --- Random Ink Blot (extra pressure at start/end of strokes) ---
            if random.random() < 0.12 * self.humanization.intensity:
                blot_x = random.randint(padding - l, padding - l + w)
                blot_y = random.randint(padding - t, padding - t + h)
                blot_radius = random.randint(1, 3)
                char_draw.ellipse(
                    [blot_x - blot_radius, blot_y - blot_radius, 
                     blot_x + blot_radius, blot_y + blot_radius],
                    fill=ink_rgb + (int(255 * min(1.0, current_pressure + 0.1)),)
                )

            # --- Elastic Distortion (unique letter shapes) ---
            quad = self.humanization.get_char_distortion_quad(canvas_w, canvas_h)
            char_img = char_img.transform((canvas_w, canvas_h), Image.QUAD, quad, resample=Image.BICUBIC)

            # --- Rotation: Character tilt + Word slant ---
            angle = self.humanization.get_char_rotation() + word_slant
            char_img = char_img.rotate(angle, resample=Image.BICUBIC, expand=True)

            # Micro offset
            dx, dy = self.humanization.get_char_offset()

            # --- Organic vertical wobble ---
            dy += self.humanization.get_baseline_wobble(current_x)

            # --- Line Curvature (slow organic arc across the page) ---
            # Simulates the hand moving in a natural pivot from the elbow/wrist
            line_arc = math.sin(current_x * 0.0005) * 8.0 * self.humanization.intensity
            dy += line_arc

            # Slant contribution (hand rising/falling)
            slant_dy = slant_per_char * char_count

            # --- Paste position maths (unchanged from original, correct) ---
            rad = math.radians(-angle)
            anchor_off_x = padding - canvas_w / 2
            anchor_off_y = padding - canvas_h / 2
            rot_off_x = (anchor_off_x * math.cos(rad)
                         - anchor_off_y * math.sin(rad))
            rot_off_y = (anchor_off_x * math.sin(rad)
                         + anchor_off_y * math.cos(rad))

            anchor_in_img_x = char_img.width  / 2 + rot_off_x
            anchor_in_img_y = char_img.height / 2 + rot_off_y

            paste_x = int(current_x - anchor_in_img_x + dx)
            paste_y = int(baseline_y - anchor_in_img_y + dy + slant_dy)

            layer.paste(char_img, (paste_x, paste_y), char_img)

            # Advance cursor (with tiny jitter)
            # For cursive fonts, we slightly tighten the spacing to simulate connections
            spacing_adj = -2 if is_script else 0
            current_x += (font.getlength(char)
                          + self.humanization.get_advance_jitter()
                          + spacing_adj)

        return current_x

    # ------------------------------------------------------------------
    # Natural-looking heading underline
    # ------------------------------------------------------------------
    def _draw_natural_underline(self,
                                 draw:    ImageDraw.Draw,
                                 start_x: float,
                                 end_x:   float,
                                 y:       float,
                                 color:   tuple) -> None:
        """
        Draw a slightly wobbly underline (thinner than original to look
        like a real pen stroke rather than a ruler-drawn line).
        """
        steps = 30
        pts   = []
        for i in range(steps + 1):
            t  = i / steps
            px = start_x + (end_x - start_x) * t
            py = y + math.sin(t * 6) * 1.5 + random.uniform(-0.8, 0.8)
            pts.append((px, py))

        for i in range(len(pts) - 1):
            p = random.uniform(0.75, 1.0)
            lc = color + (int(255 * p),)
            w  = random.choice([2, 2, 3])   # mostly 2px, occasionally 3px
            draw.line([pts[i], pts[i + 1]], fill=lc, width=w)
