import sys
import os

try:
    from PIL import Image
except ImportError:
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "Pillow"])
    from PIL import Image

def crop_mark_square(image_path, output_path):
    img = Image.open(image_path).convert("RGBA")
    width, height = img.size
    
    # Assume the mark is roughly a square on the left side
    # We will crop a box of height x height from the left
    mark_width = min(width, height * 1.2)
    cropped = img.crop((0, 0, int(mark_width), height))
    
    # Trim transparency
    cropped_data = cropped.getdata()
    cw, ch = cropped.size
    
    rows_with_pixels = []
    for y in range(ch):
        has_pixel = False
        for x in range(cw):
            if cropped_data[y * cw + x][3] > 10:
                has_pixel = True
                break
        rows_with_pixels.append(has_pixel)
        
    cols_with_pixels = []
    for x in range(cw):
        has_pixel = False
        for y in range(ch):
            if cropped_data[y * cw + x][3] > 10:
                has_pixel = True
                break
        cols_with_pixels.append(has_pixel)
        
    top = 0
    for y in range(ch):
        if rows_with_pixels[y]:
            top = y; break
            
    bottom = ch
    for y in range(ch-1, -1, -1):
        if rows_with_pixels[y]:
            bottom = y + 1; break
            
    left = 0
    for x in range(cw):
        if cols_with_pixels[x]:
            left = x; break
            
    right = cw
    for x in range(cw-1, -1, -1):
        if cols_with_pixels[x]:
            right = x + 1; break
            
    padding = 5
    top = max(0, top - padding)
    bottom = min(ch, bottom + padding)
    left = max(0, left - padding)
    right = min(cw, right + padding)
    
    final_crop = cropped.crop((left, top, right, bottom))
    final_crop.save(output_path)
    print(f"Successfully cropped mark to {output_path}")

if __name__ == "__main__":
    crop_mark_square("logo.png", "mark_only.png")
