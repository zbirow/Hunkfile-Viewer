# Wii/wii_texture_decoder.py
import struct
import numpy as np
from PIL import Image
from texture_decoder import TextureDecoder

class WiiTextureDecoder(TextureDecoder):
    def parse_texture_header(self, data):
        OFFSET_WIDTH = 0x0C
        OFFSET_HEIGHT = 0x0E
        HEADER_MIN_LENGTH = 0x16

        if len(data) >= HEADER_MIN_LENGTH:
            magic = data[:2]
            if magic == b'\xA1\xBC':
                texture_format = "CRMP"
            elif magic == b'\xE9\x78':
                texture_format = "Unknown (but showing as CRMP)"
            else:
                texture_format = f"Unknown (magic: {magic.hex().upper()})"
            width = struct.unpack('>H', data[OFFSET_WIDTH:OFFSET_WIDTH+2])[0]
            height = struct.unpack('>H', data[OFFSET_HEIGHT:OFFSET_HEIGHT+2])[0]
            return width, height, texture_format
        return 0, 0, "Unknown"

    @staticmethod
    def unpack_rgb565(color):
        color = ((color & 0xFF) << 8) | (color >> 8)
        r = ((color >> 11) & 0x1F) * 255 // 31
        g = ((color >> 5) & 0x3F) * 255 // 63
        b = (color & 0x1F) * 255 // 31
        return (r, g, b, 255)

    @staticmethod
    def decode_block(block_data, x, y, image, width, height):
        try:
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
            lookup = struct.unpack(">I", block_data[4:8])[0]
            for j in range(4):
                for i in range(4):
                    px = min(x + i, width - 1)
                    py = min(y + j, height - 1)
                    idx = (lookup >> (2 * (15 - (j * 4 + i)))) & 0x03
                    image[py, px] = colors[idx]
        except Exception as e:
            pass

    def decode_texture(self, texture_data, width, height, texture_format):
        if width == 0 or height == 0:
            return None
        try:
            image = np.zeros((height, width, 4), dtype=np.uint8)
            blocks_wide = (width + 7) // 8
            for block_idx in range(len(texture_data) // 32):
                block_y = block_idx // blocks_wide
                block_x = block_idx % blocks_wide
                block_data = texture_data[block_idx*32 : block_idx*32+32]
                for i, (dx, dy) in enumerate([(0,0), (4,0), (0,4), (4,4)]):
                    x = block_x * 8 + dx
                    y = block_y * 8 + dy
                    subblock = block_data[i*8 : i*8+8]
                    self.decode_block(subblock, x, y, image, width, height)
            return Image.fromarray(image, "RGBA")
        except Exception as e:
            print(f"Error decoding CRMP texture: {e}")
            return None
