from PIL import Image
import numpy as np
import struct
import os

class WiiTextureDecoder:
    @staticmethod
    def unpack_rgb565(color):
        """Konwersja RGB565 na RGBA8888 (identyczna jak w oryginale)"""
        color = ((color & 0xFF) << 8) | (color >> 8)
        r = ((color >> 11) & 0x1F) * 255 // 31
        g = ((color >> 5) & 0x3F) * 255 // 63
        b = (color & 0x1F) * 255 // 31
        return (r, g, b, 255)

    @staticmethod
    def decode_block(block_data, x, y, image, width, height):
        """Dekodowanie pojedynczego bloku 4x4"""
        try:
            # Little-endian dla kolorów
            color0 = struct.unpack("<H", block_data[0:2])[0]
            color1 = struct.unpack("<H", block_data[2:4])[0]
            
            rgb0 = WiiTextureDecoder.unpack_rgb565(color0)
            rgb1 = WiiTextureDecoder.unpack_rgb565(color1)

            if color0 > color1:
                rgb2 = (
                    (2 * rgb0[0] + rgb1[0] + 1) // 3,
                    (2 * rgb0[1] + rgb1[1] + 1) // 3,
                    (2 * rgb0[2] + rgb1[2] + 1) // 3,
                    255
                )
                rgb3 = (
                    (rgb0[0] + 2 * rgb1[0] + 1) // 3,
                    (rgb0[1] + 2 * rgb1[1] + 1) // 3,
                    (rgb0[2] + 2 * rgb1[2] + 1) // 3,
                    255
                )
            else:
                rgb2 = (
                    (rgb0[0] + rgb1[0] + 1) // 2,
                    (rgb0[1] + rgb1[1] + 1) // 2,
                    (rgb0[2] + rgb1[2] + 1) // 2,
                    255
                )
                rgb3 = (0, 0, 0, 0)

            colors = [rgb0, rgb1, rgb2, rgb3]
            # Big-endian dla indeksów
            lookup = struct.unpack(">I", block_data[4:8])[0]
            
            for j in range(4):
                for i in range(4):
                    px = min(x + i, width - 1)
                    py = min(y + j, height - 1)
                    idx = (lookup >> (2 * (15 - (j * 4 + i)))) & 0x03
                    image[py, px] = colors[idx]
        except Exception as e:
            pass

def decode_texture(input_path, output_path, width=1024, height=1024):
    """Główna funkcja dekodująca"""
    with open(input_path, "rb") as f:
        data = f.read()
    
    image = np.zeros((height, width, 4), dtype=np.uint8)
    blocks_wide = (width + 7) // 8
    
    for block_idx in range(len(data) // 32):
        block_y = block_idx // blocks_wide
        block_x = block_idx % blocks_wide
        block_data = data[block_idx*32 : block_idx*32+32]
        
        # 4 podbloki 4x4 w każdym bloku 8x8
        for i, (dx, dy) in enumerate([(0,0), (4,0), (0,4), (4,4)]):
            x = block_x * 8 + dx
            y = block_y * 8 + dy
            subblock = block_data[i*8 : i*8+8]
            WiiTextureDecoder.decode_block(subblock, x, y, image, width, height)
    
    Image.fromarray(image, "RGBA").save(output_path)

if __name__ == "__main__":
    # Konfiguracja
    INPUT_DIR = r"c:\Users\pawel\Desktop\leon\output_dds\ninja\font\wii"
    OUTPUT_DIR = os.path.join(INPUT_DIR, "decoded_simple")
    
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    for filename in os.listdir(INPUT_DIR):
        if filename.lower().endswith(".dat"):
            input_file = os.path.join(INPUT_DIR, filename)
            output_file = os.path.join(OUTPUT_DIR, f"{os.path.splitext(filename)[0]}.png")
            
            decode_texture(input_file, output_file, 1024, 1024)
            print(f"Zdekodowano: {filename} -> {os.path.basename(output_file)}")