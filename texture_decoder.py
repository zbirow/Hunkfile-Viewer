# texture_decoder.py
from abc import ABC, abstractmethod
from PIL import Image

class TextureDecoder(ABC):
    @abstractmethod
    def decode_texture(self, texture_data, width, height, texture_format):
        """Decode texture data and return a PIL Image."""
        pass

    @abstractmethod
    def parse_texture_header(self, data):
        """Parse texture header and return (width, height, texture_format)."""
        pass