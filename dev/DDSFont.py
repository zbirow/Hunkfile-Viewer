import os

def create_dds_header(width, height, format="DXT5", mip_count=0):
    # Tworzy nagłówek DDS dla podanych wymiarów, formatu i liczby mipmap
    header = bytearray(128)
    
    # Magiczny nagłówek DDS
    header[0:4] = b"DDS "
    
    # Rozmiar nagłówka (zawsze 124)
    header[4:8] = (124).to_bytes(4, "little")
    
    # Flagi (DDSD_CAPS | DDSD_HEIGHT | DDSD_WIDTH | DDSD_PIXELFORMAT | DDSD_LINEARSIZE)
    flags = 0x1 | 0x2 | 0x4 | 0x1000 | 0x80000  # Dodano DDSD_LINEARSIZE
    if mip_count > 0:
        flags |= 0x8000  # DDSD_MIPMAPCOUNT
    header[8:12] = flags.to_bytes(4, "little")
    
    # Wysokość i szerokość
    header[12:16] = height.to_bytes(4, "little")
    header[16:20] = width.to_bytes(4, "little")
    
    # Rozmiar liniowy (dla DXT5: rozmiar danych tekstury)
    linear_size = (width * height) // 2  # 262144 dla 1024x256
    header[20:24] = linear_size.to_bytes(4, "little")
    
    # Głębokość (0 dla tekstur 2D)
    header[24:28] = (0).to_bytes(4, "little")
    
    # Liczba mipmap
    header[28:32] = mip_count.to_bytes(4, "little")
    
    # Zarezerwowane pola (puste)
    header[32:76] = (0).to_bytes(44, "little")
    
    # Rozmiar struktury PixelFormat (zawsze 32)
    header[76:80] = (32).to_bytes(4, "little")
    
    # Flagi PixelFormat (DDPF_FOURCC dla DXT5)
    header[80:84] = (0x4).to_bytes(4, "little")
    
    # FourCC dla DXT5
    header[84:88] = b"DXT5"
    
    # Pozostałe pola PixelFormat (RGBBitCount, maski itp. - 0 dla DXT5)
    header[88:108] = (0).to_bytes(20, "little")
    
    # Flagi Caps (DDSCAPS_TEXTURE)
    caps = 0x1000
    if mip_count > 0:
        caps |= 0x400008  # DDSCAPS_MIPMAP | DDSCAPS_COMPLEX
    header[108:112] = caps.to_bytes(4, "little")
    
    # Pozostałe pola Caps (puste)
    header[112:128] = (0).to_bytes(16, "little")
    
    return header

def extract_texture_to_dds(input_filename, output_filename, offset, texture_size, width, height, mip_count=0):
    # Pobierz katalog, w którym znajduje się skrypt
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Utwórz pełną ścieżkę do pliku wejściowego
    input_file = os.path.join(script_dir, input_filename)
    
    # Utwórz pełną ścieżkę do pliku wyjściowego
    output_file = os.path.join(script_dir, output_filename)
    
    # Sprawdzenie, czy plik wejściowy istnieje
    if not os.path.exists(input_file):
        print(f"Błąd: Plik {input_file} nie istnieje w katalogu {script_dir}!")
        return
    
    # Odczyt danych tekstury
    try:
        with open(input_file, "rb") as f:
            f.seek(offset)  # Przejdź do offsetu
            texture_data = f.read(texture_size)  # Odczytaj dane tekstury
            
            # Sprawdzenie, czy odczytano wystarczającą ilość danych
            if len(texture_data) < texture_size:
                print(f"Uwaga: Odczytano tylko {len(texture_data)} bajtów, oczekiwano {texture_size}.")
                # Dopełnij danymi, jeśli za mało
                texture_data += b"\x00" * (texture_size - len(texture_data))
            
            # Generowanie nagłówka DDS
            header = create_dds_header(width, height, "DXT5", mip_count)
            
            # Zapis pliku DDS
            with open(output_file, "wb") as out:
                out.write(header)  # Zapisz nagłówek
                out.write(texture_data)  # Zapisz dane tekstury
            print(f"Plik DDS zapisano jako {output_file}")
            
    except Exception as e:
        print(f"Błąd podczas przetwarzania: {e}")

# Parametry z logu
input_filename = "input.dat"  # Zastąp nazwą pliku gry w tym samym katalogu co skrypt
output_filename = "texture2.dds"  # Nazwa pliku wyjściowego
offset = 0  # Offset z logu
texture_size = 262144  # Rozmiar z logu ("size on preview")
width = 1024  # Szerokość z logu
height = 256  # Wysokość z logu
mip_count = 0  # Brak mipmap, zgodnie z logiem

# Wywołanie funkcji
extract_texture_to_dds(input_filename, output_filename, offset, texture_size, width, height, mip_count)