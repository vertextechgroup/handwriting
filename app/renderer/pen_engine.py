import random
from PIL import Image, ImageFilter, ImageEnhance


class PenEngine:
    """
    Simulates various pen and pencil styles with realistic ink/graphite behavior.

    Supported styles:
        "gel"        – smooth dark-blue gel ink (default, matches sample image)
        "ballpoint"  – lighter, slightly smeared blue/black
        "fountain"   – wider ink spread, more contrast
        "pencil"     – graphite grey, lower opacity, grainier
    """

    PEN_STYLES = {
        "gel": {
            "blur": 0.35,
            "contrast": 1.25,
            "opacity": 0.96,
            "noise_mix": 0.08,
        },
        "ballpoint": {
            "blur": 0.15,
            "contrast": 1.05,
            "opacity": 0.82,
            "noise_mix": 0.12,
        },
        "fountain": {
            "blur": 0.55,
            "contrast": 1.45,
            "opacity": 0.92,
            "noise_mix": 0.06,
        },
        "pencil": {
            "blur": 0.8,
            "contrast": 0.88,
            "opacity": 0.72,
            "noise_mix": 0.20,
        },
    }

    # Default ink colour: dark navy-blue (matches sample handwriting)
    DEFAULT_COLOR = "#000080"

    def __init__(self, style: str = "gel", color: str = "#000080"):
        self.style_name = style
        self.style = self.PEN_STYLES.get(style, self.PEN_STYLES["gel"])
        self.color = color or self.DEFAULT_COLOR

    # ------------------------------------------------------------------
    # Apply post-render ink effects to the text layer
    # ------------------------------------------------------------------
    def apply_ink_effect(self, text_layer: Image.Image) -> Image.Image:
        """
        Apply layered ink effects:
          1. Dilation      – simulates ink spread on absorbent paper
          2. Gaussian blur  – simulates ink bleed into paper fibres
          3. Smudge effect  – directional motion blur for realistic ink smearing
          4. Contrast boost – ink density / darkness variation
          5. Alpha noise    – micro pressure variation (lighter patches)
        """
        if text_layer.mode != "RGBA":
            text_layer = text_layer.convert("RGBA")

        # 1. Dilation (ink spread)
        if self.style_name in ("fountain", "gel"):
            text_layer = text_layer.filter(ImageFilter.MaxFilter(3))

        # 2. Blur (ink bleed)
        blur_r = self.style["blur"]
        if blur_r > 0:
            text_layer = text_layer.filter(
                ImageFilter.GaussianBlur(radius=blur_r)
            )

        # 3. Smudge effect (simulates hand moving over wet ink)
        if self.style_name in ("gel", "ballpoint") and random.random() < 0.3:
            # Small directional blur
            text_layer = text_layer.filter(ImageFilter.BoxBlur(0.4))
            # Slightly shift the layer to one side
            shift_layer = Image.new("RGBA", text_layer.size, (0, 0, 0, 0))
            shift_layer.paste(text_layer, (random.randint(1, 2), 0))
            text_layer = Image.blend(text_layer, shift_layer, 0.4)

        # 4. Contrast
        enhancer = ImageEnhance.Contrast(text_layer)
        text_layer = enhancer.enhance(self.style["contrast"] + random.uniform(-0.05, 0.05))

        # 5. Alpha-channel noise (simulates pressure micro-variation)
        noise_mix = self.style["noise_mix"]
        if noise_mix > 0:
            w, h = text_layer.size
            # Build a small noise map and upscale
            noise_w, noise_h = max(1, w // 12), max(1, h // 12)
            noise = Image.new("L", (noise_w, noise_h))
            noise_data = bytes(
                [random.randint(210, 255) for _ in range(noise_w * noise_h)]
            )
            noise.frombytes(noise_data)
            noise = noise.resize((w, h), resample=Image.BILINEAR)

            r, g, b, a = text_layer.split()
            a = Image.blend(a, noise, noise_mix)
            text_layer = Image.merge("RGBA", (r, g, b, a))

        return text_layer

    # ------------------------------------------------------------------
    # Colour conversion
    # ------------------------------------------------------------------
    def get_color_rgb(self) -> tuple:
        """Convert hex colour string to (R, G, B) int tuple."""
        hex_color = self.color.lstrip("#")
        if len(hex_color) == 3:
            hex_color = "".join(c * 2 for c in hex_color)
        try:
            return tuple(int(hex_color[i: i + 2], 16) for i in (0, 2, 4))
        except ValueError:
            return (0, 0, 128)   # fallback: navy blue

    # ------------------------------------------------------------------
    # Pencil style: apply a cross-hatch/grain overlay for graphite feel
    # ------------------------------------------------------------------
    def apply_pencil_grain(self, text_layer: Image.Image) -> Image.Image:
        """Extra graphite-grain pass for 'pencil' style only."""
        if self.style_name != "pencil":
            return text_layer
        w, h = text_layer.size
        grain = Image.new("L", (w // 4, h // 4))
        g_data = bytes([random.randint(180, 255) for _ in range((w // 4) * (h // 4))])
        grain.frombytes(g_data)
        grain = grain.resize((w, h), resample=Image.NEAREST)
        r, g, b, a = text_layer.split()
        a = Image.blend(a, grain, 0.15)
        return Image.merge("RGBA", (r, g, b, a))
