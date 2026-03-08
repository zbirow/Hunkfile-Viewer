# PC/pc_texture_decoder.py
import struct
import io
import numpy as np
from PIL import Image
from texture_decoder import TextureDecoder

class PCTextureDecoder(TextureDecoder):
    def parse_texture_header(self, data):
        OFFSET_WIDTH = 0x30
        OFFSET_HEIGHT = 0x32
        HEADER_MIN_LENGTH = 0x32

        if len(data) >= HEADER_MIN_LENGTH:
            width = struct.unpack('<H', data[OFFSET_WIDTH:OFFSET_WIDTH+2])[0]
            height = struct.unpack('<H', data[OFFSET_HEIGHT:OFFSET_HEIGHT+2])[0]
            texture_format = "DXT1"
            if len(data) >= 0x40:
                format_section = data[0x34:0x40]
                
                if b'DXT5' in format_section:
                    texture_format = "DXT5"
                elif b'DXT1' in format_section:
                    texture_format = "DXT1"
                else:
                    texture_format = "R8G8B8A8"  # wszystko inne traktujemy jako R8G8B8A8
                
                return width, height, texture_format
            return 0, 0, "DXT1"  # domyślnie DXT1 jeśli plik jest za krótki
    def create_dds_header(self, width, height, texture_format, mip_count=0):
        header = bytearray(128)
        header[0:4] = b"DDS "
        header[4:8] = (124).to_bytes(4, "little")
        flags = 0x1 | 0x2 | 0x4 | 0x1000
        if texture_format in ["DXT1", "DXT5"]:
            flags |= 0x80000
            linear_size = self.calculate_compressed_size(width, height, texture_format)
            pitch_or_linear_size_value = linear_size
        else:
            flags |= 0x8
            pitch_or_linear_size_value = width * 4
        if mip_count > 0:
            flags |= 0x20000
        header[8:12] = flags.to_bytes(4, "little")
        header[12:16] = height.to_bytes(4, "little")
        header[16:20] = width.to_bytes(4, "little")
        header[20:24] = pitch_or_linear_size_value.to_bytes(4, "little")
        header[24:28] = (0).to_bytes(4, "little")
        header[28:32] = mip_count.to_bytes(4, "little")
        header[76:80] = (32).to_bytes(4, "little")
        if texture_format in ["DXT1", "DXT5"]:
            header[80:84] = (0x4).to_bytes(4, "little")
            header[84:88] = texture_format.encode('ascii')
        elif texture_format == "R8G8B8A8":
            header[80:84] = (0x41).to_bytes(4, "little")
            header[88:92] = (32).to_bytes(4, "little")
            header[92:96] = (0x00FF0000).to_bytes(4, "little")
            header[96:100] = (0x0000FF00).to_bytes(4, "little")
            header[100:104] = (0x000000FF).to_bytes(4, "little")
            header[104:108] = (0xFF000000).to_bytes(4, "little")
        caps1 = 0x1000
        if mip_count > 0:
            caps1 |= 0x400008
        header[108:112] = caps1.to_bytes(4, "little")
        return header

    def calculate_compressed_size(self, width, height, texture_format):
        block_size = 8 if texture_format == "DXT1" else 16
        num_blocks_wide = max(1, (width + 3) // 4)
        num_blocks_high = max(1, (height + 3) // 4)
        return num_blocks_wide * num_blocks_high * block_size

    def decode_texture(self, texture_data, width, height, texture_format):
        if width == 0 or height == 0:
            return None
        try:
            dds_header = self.create_dds_header(width, height, texture_format)
            dds_data = dds_header + texture_data
            with io.BytesIO(dds_data) as dds_file:
                img = Image.open(dds_file)
                img = img.convert("RGBA")
                return img
        except Exception as e:
            print(f"Error decoding PC texture: {e}")
            return None
