import os
from PIL import Image, ImageDraw, ImageFilter

def create_chirp_icon():
    base_dir = r"c:\Users\mishr\Downloads\SEO Facebook\Chirp"
    os.makedirs(base_dir, exist_ok=True)
    size = 512
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # 1. Multi-tone ambient glow (Cyan + Violet representing OpenAI & Gemini)
    draw.rounded_rectangle([20, 20, size - 20, size - 20], radius=120, fill=(16, 185, 129, 40))
    draw.rounded_rectangle([35, 35, size - 35, size - 35], radius=110, fill=(139, 92, 246, 40))
    img = img.filter(ImageFilter.GaussianBlur(16))
    draw = ImageDraw.Draw(img)

    # 2. Main chassis - Dark obsidian titanium
    chassis = [46, 46, size - 46, size - 46]
    draw.rounded_rectangle(chassis, radius=110, fill=(11, 15, 25, 255), outline=(38, 48, 70, 255), width=4)

    # Dual-tone rim
    draw.rounded_rectangle([52, 52, size - 52, size - 52], radius=104, outline=(16, 185, 129, 130), width=2)

    cx, cy = size // 2, size // 2 - 20

    # 3. Futuristic Mic Capsule
    mic_w = 76
    mic_h = 136
    mic_box = [cx - mic_w // 2, cy - mic_h // 2, cx + mic_w // 2, cy + mic_h // 2]
    draw.rounded_rectangle(mic_box, radius=38, fill=(22, 28, 44, 255), outline=(0, 245, 155, 230), width=4)

    # Sound grilles
    for gy in range(cy - 44, cy + 22, 16):
        draw.line([(cx - 26, gy), (cx + 26, gy)], fill=(0, 245, 155, 180), width=3)

    # Mic stand cradle arc (with gradient look)
    arc_box = [cx - 70, cy - 24, cx + 70, cy + 96]
    draw.arc(arc_box, start=0, end=180, fill=(139, 92, 246, 240), width=6)

    # Base stem & footing
    draw.line([(cx, cy + 96), (cx, cy + 138)], fill=(139, 92, 246, 240), width=6)
    draw.line([(cx - 50, cy + 138), (cx + 50, cy + 138)], fill=(139, 92, 246, 240), width=8)

    # Sparkling AI Energy Waves (OpenAI Emerald on left, Gemini Violet on right)
    # Left waves (OpenAI)
    for x_off, alpha in [(-105, 210), (-135, 130)]:
        x = cx + x_off
        draw.line([(x, cy - 35), (x, cy + 35)], fill=(16, 185, 129, alpha), width=5)
    # Right waves (Gemini)
    for x_off, alpha in [(105, 210), (135, 130)]:
        x = cx + x_off
        draw.line([(x, cy - 35), (x, cy + 35)], fill=(139, 92, 246, alpha), width=5)

    # Save PNG
    png_path = os.path.join(base_dir, "chirp_logo.png")
    img.save(png_path, "PNG")
    print(f"Saved: {png_path}")

    # Generate multi-size ICO
    ico_path = os.path.join(base_dir, "chirp.ico")
    sizes = [(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)]
    img.save(ico_path, format="ICO", sizes=sizes)
    print(f"Saved: {ico_path}")

if __name__ == "__main__":
    create_chirp_icon()
