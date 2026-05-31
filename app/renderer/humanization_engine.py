import random
import math


class HumanizationEngine:
    """
    Injects human-like imperfections and randomness into the rendering process.
    Tuned to match real handwriting: slight baseline drift, variable letter
    spacing and pressure, and gentle per-character rotation.
    """

    def __init__(self, intensity: float = 1.0):
        self.intensity = intensity
        # Fatigue increases as the hand writes more — affects size and messiness
        self._fatigue = 0.0
        self._word_count = 0
        self._line_count = 0

    # ------------------------------------------------------------------
    # Per-page reset so each page starts fresh
    # ------------------------------------------------------------------
    def reset_page(self):
        self._fatigue = 0.0
        self._word_count = 0
        self._line_count = 0

    def update_fatigue(self, line_index: int, total_lines: int):
        """Increase fatigue as we move down the page."""
        self._line_count = line_index
        # Fatigue is 0.0 at top, up to 0.4 at bottom of page
        self._fatigue = (line_index / max(1, total_lines)) * 0.4 * self.intensity

    # ------------------------------------------------------------------
    # Slow drift: simulates hand moving slightly up/down over a line
    # ------------------------------------------------------------------
    def get_line_drift(self) -> float:
        """Vertical drift for the *whole* line (applied once per line)."""
        # Drift increases with fatigue
        multiplier = 1.0 + self._fatigue
        return random.gauss(0, 1.8 * multiplier) * self.intensity

    # ------------------------------------------------------------------
    # Per-character vertical micro-jitter (within a line)
    # ------------------------------------------------------------------
    def get_char_vertical_jitter(self) -> float:
        """Small vertical bounce per character — keeps baseline organic."""
        return random.gauss(0, 0.9) * self.intensity

    # ------------------------------------------------------------------
    # Character rotation — small tilt, occasionally more pronounced
    # ------------------------------------------------------------------
    def get_char_rotation(self) -> float:
        """
        Most characters tilt ±1.5°; occasionally (1-in-10) one tilts up to ±4°.
        Rotation variance increases with fatigue.
        """
        multiplier = 1.0 + self._fatigue * 2.0
        base = random.gauss(0, 1.2 * multiplier) * self.intensity
        if random.random() < (0.10 + self._fatigue * 0.2):          # occasional stronger tilt
            base += random.uniform(-3.0, 3.0) * self.intensity * multiplier
        return max(-6.0, min(6.0, base))

    # ------------------------------------------------------------------
    # Character elastic distortion
    # ------------------------------------------------------------------
    def get_char_distortion_quad(self, w: int, h: int) -> tuple:
        """
        Return 8-tuple for Image.QUAD transform.
        Slightly distorts the character corners for unique shapes.
        """
        d = 1.2 * self.intensity * (1.0 + self._fatigue)
        # Quad format: (x0, y0, x1, y1, x2, y2, x3, y3)
        # where (x0, y0) is top-left, (x1, y1) bottom-left, etc.
        return (
            random.uniform(-d, d), random.uniform(-d, d),
            random.uniform(-d, d), h + random.uniform(-d, d),
            w + random.uniform(-d, d), h + random.uniform(-d, d),
            w + random.uniform(-d, d), random.uniform(-d, d)
        )

    # ------------------------------------------------------------------
    # Character horizontal micro-offset
    # ------------------------------------------------------------------
    def get_char_offset(self) -> tuple:
        """
        Tiny (x, y) nudge.  x keeps letter spacing slightly uneven;
        y adds vertical micro-jitter on top of the line drift.
        """
        dx = random.gauss(0, 0.7) * self.intensity
        dy = self.get_char_vertical_jitter()
        return dx, dy

    # ------------------------------------------------------------------
    # Word spacing variation
    # ------------------------------------------------------------------
    def get_word_spacing_jitter(self) -> float:
        """
        Word gaps vary naturally.  Track word count to simulate writing
        getting slightly denser as the hand tires.
        """
        self._word_count += 1
        # Very mild compression over 30+ words on a line
        fatigue_offset = -min(self._word_count * 0.05, 2.0)
        # Variance increases with fatigue
        multiplier = 1.0 + self._fatigue
        return random.gauss(fatigue_offset, 3.5 * multiplier) * self.intensity

    # ------------------------------------------------------------------
    # Ink pressure / opacity variation
    # ------------------------------------------------------------------
    def get_pressure_variation(self) -> float:
        """
        Gel pen: mostly consistent but dips occasionally.
        Pressure dips more frequently with fatigue.
        """
        mean = 0.94 - (self._fatigue * 0.1)
        base = random.gauss(mean, 0.04 * (1.0 + self._fatigue))
        return max(0.70, min(1.0, base))

    # ------------------------------------------------------------------
    # Cursor advance correction (kerning-like)
    # ------------------------------------------------------------------
    def get_advance_jitter(self) -> float:
        """Extra pixels added/subtracted to the cursor after each character."""
        multiplier = 1.0 + self._fatigue
        return random.gauss(0, 0.4 * multiplier) * self.intensity

    # ------------------------------------------------------------------
    # Character scaling — slight variation in size
    # ------------------------------------------------------------------
    def get_char_scale(self) -> float:
        """
        Most characters are 100% size; occasionally ±3% variation.
        """
        multiplier = 1.0 + self._fatigue
        return max(0.92, min(1.08, random.gauss(1.0, 0.02 * self.intensity * multiplier)))

    # ------------------------------------------------------------------
    # Per-word slant — hand angle shifts slightly per word
    # ------------------------------------------------------------------
    def get_word_slant(self) -> float:
        """
        Whole word tilt variation (±1.5°).
        Word slant increases as writing progresses.
        """
        multiplier = 1.0 + self._fatigue * 1.5
        return random.gauss(0, 1.0 * multiplier) * self.intensity

    # ------------------------------------------------------------------
    # Baseline wobble — more complex sine-wave based movement
    # ------------------------------------------------------------------
    def get_baseline_wobble(self, x: float) -> float:
        """
        Organic vertical wobble that changes with x position.
        """
        # Mix of two sine waves for more natural feel
        w1 = math.sin(x * 0.04) * 1.2
        w2 = math.sin(x * 0.01) * 2.0
        return (w1 + w2) * self.intensity

    # ------------------------------------------------------------------
    # Line-level slant: whole line tilts slightly upward or downward
    # ------------------------------------------------------------------
    def get_line_slant_per_char(self, char_index: int) -> float:
        """
        Simulate the hand rising or falling across a line.
        Returns the y-offset contribution for character at `char_index`.
        """
        # Slant direction chosen once per engine instance but changes sign rarely
        slant_rate = random.gauss(0, 0.04) * self.intensity   # pixels per character
        return slant_rate * char_index
