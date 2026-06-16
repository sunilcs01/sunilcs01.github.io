import sys
import os

try:
    from PIL import Image
except ImportError:
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "Pillow"])
    from PIL import Image

def crop_mark(image_path, output_path):
    img = Image.open(image_path).convert("RGBA")
    width, height = img.size
    
    data = img.getdata()
    
    cols_with_pixels = []
    for x in range(width):
        has_pixel = False
        for y in range(height):
            if data[y * width + x][3] > 10:
                has_pixel = True
                break
        cols_with_pixels.append(has_pixel)
        
    in_group = False
    groups = []
    current_group_start = -1
    
    for x in range(width):
        if cols_with_pixels[x]:
            if not in_group:
                in_group = True
                current_group_start = x
        else:
            if in_group:
                in_group = False
                groups.append((current_group_start, x))
                
    if in_group:
        groups.append((current_group_start, width))
        
    if not groups:
        print("No non-transparent pixels found. Image might be empty.")
        return False
        
    # Assume gap > 0.5% of width is a real separator between mark and text
    gap_threshold = width * 0.005
    merged_groups = []
    current_merged = [groups[0][0], groups[0][1]]
    
    for i in range(1, len(groups)):
        start, end = groups[i]
        gap = start - current_merged[1]
        if gap < gap_threshold:
            current_merged[1] = end
        else:
            merged_groups.append(current_merged)
            current_merged = [start, end]
    merged_groups.append(current_merged)
    
    print(f"Found {len(merged_groups)} main horizontal elements.")
    
    # We will crop the first element assuming it's the mark on the left
    mark_start_x, mark_end_x = merged_groups[0]
    
    # Expand slightly for padding
    padding = 5
    mark_start_x = max(0, mark_start_x - padding)
    mark_end_x = min(width, mark_end_x + padding)
    
    cropped = img.crop((mark_start_x, 0, mark_end_x, height))
    
    # Now crop vertically to remove empty space
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
        
    top = 0
    for y in range(ch):
        if rows_with_pixels[y]:
            top = y
            break
            
    bottom = ch
    for y in range(ch-1, -1, -1):
        if rows_with_pixels[y]:
            bottom = y + 1
            break
            
    top = max(0, top - padding)
    bottom = min(ch, bottom + padding)
    
    final_crop = cropped.crop((0, top, cw, bottom))
    final_crop.save(output_path)
    print(f"Successfully cropped mark to {output_path}")
    return True

if __name__ == "__main__":
    crop_mark("logo.png", "mark_only.png")
