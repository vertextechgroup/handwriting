import os
import random
import logging
from PIL import Image, ImageFilter, ImageEnhance, ImageOps

logger = logging.getLogger(__name__)

class ImageProcessor:
    @staticmethod
    def apply_ink_bleed(image: Image.Image, amount: float = 0.5) -> Image.Image:
        """Simulate ink bleeding into paper fibers."""
        if amount <= 0:
            return image
        # Subtle blur to soften edges
        return image.filter(ImageFilter.GaussianBlur(radius=amount))

    @staticmethod
    def add_subtle_noise(image: Image.Image, intensity: int = 5) -> Image.Image:
        """Add subtle grain/noise to the image efficiently."""
        if intensity <= 0:
            return image
        
        # Create a small noise image and scale it up to the size of the original
        # This creates a more natural "grain" look than per-pixel noise
        width, height = image.size
        noise_size = (width // 2, height // 2)
        noise = Image.new('L', noise_size)
        
        # Fill with random values
        noise_data = bytes([random.randint(128 - intensity, 128 + intensity) for _ in range(noise_size[0] * noise_size[1])])
        noise.frombytes(noise_data)
        
        # Scale up and blur slightly for organic look
        noise = noise.resize((width, height), resample=Image.BILINEAR)
        noise = noise.filter(ImageFilter.GaussianBlur(radius=1.0))
        
        # Overlay noise on the image
        if image.mode != 'RGB':
            image = image.convert('RGB')
            
        # Blend noise with the image (using it as a luminosity map)
        noise = ImageOps.colorize(noise, black="black", white="white")
        return Image.blend(image, noise, 0.1)

    @staticmethod
    def add_paper_texture(image: Image.Image) -> Image.Image:
        """Add a subtle paper texture background efficiently."""
        width, height = image.size
        
        # 1. Base paper color (slightly warm off-white)
        paper = Image.new('RGB', (width, height), color=(252, 251, 248))
        
        # 2. Create synthetic fiber texture
        tex_w, tex_h = width // 4, height // 4
        texture_layer = Image.new('L', (tex_w, tex_h), color=128)
        
        from PIL import ImageDraw
        draw = ImageDraw.Draw(texture_layer)
        for _ in range(200):
            x1 = random.randint(0, tex_w)
            y1 = random.randint(0, tex_h)
            length = random.randint(1, 3)
            angle = random.uniform(0, 360)
            import math
            x2 = x1 + length * math.cos(angle)
            y2 = y1 + length * math.sin(angle)
            draw.line([(x1, y1), (x2, y2)], fill=random.randint(100, 150), width=1)
            
        texture_layer = texture_layer.resize((width, height), resample=Image.BILINEAR)
        texture_layer = texture_layer.filter(ImageFilter.GaussianBlur(radius=0.5))
        
        texture_img = ImageOps.colorize(texture_layer, black=(240, 235, 225), white=(255, 255, 255))
        paper = Image.blend(paper, texture_img, 0.2)
        
        # 3. Composite handwriting over paper
        if image.mode != 'RGBA':
            image = image.convert('RGBA')
            
        # Create a "variable ink" mask
        ink_mask = Image.new('L', (width, height), color=255)
        mask_draw = Image.new('L', (width // 10, height // 10))
        # Fill mask_draw with some clouds
        for x in range(width // 10):
            for y in range(height // 10):
                mask_draw.putpixel((x, y), random.randint(200, 255))
        mask_draw = mask_draw.resize((width, height), resample=Image.BILINEAR)
        
        datas = image.getdata()
        new_data = []
        
        # Cache random values for speed
        for i, item in enumerate(datas):
            # item is (R, G, B, A)
            avg = (item[0] + item[1] + item[2]) / 3
            if avg > 230:
                new_data.append((255, 255, 255, 0))
            else:
                # Variable ink density
                m = mask_draw.getpixel((i % width, i // width)) / 255.0
                # Slightly vary the color
                r = int(item[0] * (0.9 + 0.1 * m))
                g = int(item[1] * (0.9 + 0.1 * m))
                b = int(item[2] * (0.9 + 0.1 * m))
                new_data.append((r, g, b, item[3]))
                
        image.putdata(new_data)
        
        paper.paste(image, (0, 0), image)
        return paper

    @staticmethod
    def apply_realism(image_path: str, output_path: str = None) -> str:
        """Apply a suite of enhancements to make the handwriting look real."""
        if output_path is None:
            output_path = image_path

        try:
            with Image.open(image_path) as img:
                # 0. Resize to a standard A4 resolution (150 DPI) for consistency
                # A4 at 150 DPI is 1240 x 1754
                target_size = (1240, 1754)
                if img.size != target_size:
                    # Maintain aspect ratio by padding instead of stretching
                    img.thumbnail(target_size, Image.Resampling.LANCZOS)
                    new_img = Image.new('RGB', target_size, color='white')
                    # Center the image
                    offset = ((target_size[0] - img.size[0]) // 2, (target_size[1] - img.size[1]) // 2)
                    new_img.paste(img, offset)
                    img = new_img

                # 1. Add paper texture and off-white background
                img = ImageProcessor.add_paper_texture(img)
                
                # 2. Simulate ink bleed
                img = ImageProcessor.apply_ink_bleed(img, amount=0.4)
                
                # 3. Add subtle noise/grain
                img = ImageProcessor.add_subtle_noise(img, intensity=3)
                
                # 4. Adjust contrast and brightness slightly
                enhancer = ImageEnhance.Contrast(img)
                img = enhancer.enhance(1.1)
                
                enhancer = ImageEnhance.Brightness(img)
                img = enhancer.enhance(0.98)
                
                # 4. Add very slight rotation (0.1 to 0.3 degrees) to simulate scanning
                angle = random.uniform(-0.2, 0.2)
                img = img.rotate(angle, resample=Image.BICUBIC, expand=False, fillcolor=(250, 249, 245))

                # 5. Save the result
                img.save(output_path, "PNG", quality=95)
                return output_path
        except Exception as e:
            logger.error(f"Error processing image {image_path}: {e}")
            return image_path
