from typing import Tuple, List


class LayoutEngine:
    """
    Manages A4 page layout, margins, and coordinate mapping.

    The layout is tuned to match PaperEngine's ruling grid:
      - Ruled lines start at y=380, spacing=80 (300 DPI)
      - Left writing margin is PAST the red margin line (~1/6 of width)
      - Right margin leaves 160 px of padding

    This ensures rendered text sits on — not between — the blue lines.
    """

    # ------------------------------------------------------------------ DPI presets
    A4_WIDTH_300  = 2480
    A4_HEIGHT_300 = 3508
    A4_WIDTH_600  = 4960
    A4_HEIGHT_600 = 7016

    def __init__(self,
                 dpi: int = 300,
                 margins: Tuple[int, int, int, int] = (380, 160, 160, 440)):
        """
        margins = (top, right, bottom, left) in pixels at 300 DPI.

        Default top = 380 matches PaperEngine's first ruled line.
        Default left = 440 (≈ margin_x + a little padding) keeps text
          to the right of the red margin line.
        """
        self.dpi = dpi
        if dpi == 600:
            self.width  = self.A4_WIDTH_600
            self.height = self.A4_HEIGHT_600
            self.margins = tuple(m * 2 for m in margins)
        else:
            self.width  = self.A4_WIDTH_300
            self.height = self.A4_HEIGHT_300
            self.margins = margins

        (self.top_margin,
         self.right_margin,
         self.bottom_margin,
         self.left_margin) = self.margins

        self.writing_width  = self.width  - self.left_margin - self.right_margin
        self.writing_height = self.height - self.top_margin  - self.bottom_margin

    # ------------------------------------------------------------------
    def get_line_coordinates(self,
                             line_index: int,
                             line_spacing: int = 80) -> Tuple[int, int]:
        """
        Return (x, y) for the START of a line.

        y is the TOP of the line slot; the HandwritingEngine positions
        the baseline at y + ascent, so characters sit ON the ruled line.
        """
        x = self.left_margin
        y = self.top_margin + (line_index * line_spacing)
        return x, y

    def get_baselines(self, line_spacing: int = 80) -> List[int]:
        """Generate y-coordinates for all ruled lines (for reference/debug)."""
        baselines = []
        y = self.top_margin
        while y < (self.height - self.bottom_margin):
            baselines.append(y)
            y += line_spacing
        return baselines

    @property
    def line_spacing_px(self) -> int:
        """The canonical line spacing in pixels at this DPI."""
        return 80 if self.dpi == 300 else 160
