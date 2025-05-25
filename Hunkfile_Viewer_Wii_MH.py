import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from tkinter.scrolledtext import ScrolledText
import struct
import io
from PIL import Image, ImageTk
import numpy as np

# Define record type constants
RECORD_TYPE_FILENAME = 0x40071
RECORD_TYPE_TEXTURE_HEADER = 0x41150
RECORD_TYPE_TEXTURE_DATA = 0x202151  # WII

class WiiTextureDecoder:
    @staticmethod
    def unpack_rgb565(color):
        """Konwersja RGB565 na RGBA8888"""
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

class HunkfileViewer:
    def __init__(self, root):
        self.root = root
        self.root.title("Hunkfile Viewer")

        self.records = []  # Stores all parsed records from the HNK file
        self.current_file = None  # Path to the currently opened HNK file
        self.texture_image = None  # Holds the PhotoImage object for the texture preview
        self.textures = {} # Dictionary to store texture metadata and data

        self.create_widgets()

    def create_widgets(self):
        # Main container with a sash (PanedWindow) for resizable panels
        main_panel = tk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        main_panel.pack(fill=tk.BOTH, expand=True)

        # Left panel - for record tree and action buttons
        left_panel = tk.Frame(main_panel, width=300)
        main_panel.add(left_panel)

        # Right panel - for record details and texture preview
        right_panel = tk.PanedWindow(main_panel, orient=tk.VERTICAL)
        main_panel.add(right_panel)

        # Button frame within the left panel
        button_frame = tk.Frame(left_panel)
        button_frame.pack(fill=tk.X, padx=5, pady=5)

        open_button = tk.Button(button_frame, text="Open HNK File", command=self.open_file)
        open_button.pack(side=tk.LEFT, expand=True)

        # Treeview to display HNK file records
        self.tree = ttk.Treeview(left_panel, columns=("Type", "Size", "Details"), show="headings")
        self.tree.heading("Type", text="Record Type")
        self.tree.heading("Size", text="Record Size")
        self.tree.heading("Details", text="Details")
        self.tree.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Details panel (ScrolledText) within the right panel
        details_frame = tk.Frame(right_panel)
        right_panel.add(details_frame)

        self.details = ScrolledText(details_frame, height=10)
        self.details.pack(fill=tk.BOTH, expand=True)

        # Texture preview panel (LabelFrame with Canvas) within the right panel
        self.texture_frame = tk.LabelFrame(right_panel, text="Texture Preview", height=400)
        right_panel.add(self.texture_frame)

        self.canvas = tk.Canvas(self.texture_frame, bg='white')
        self.canvas.pack(fill=tk.BOTH, expand=True)

        # Scrollbars for the texture preview canvas
        self.scrollbar_y = tk.Scrollbar(self.texture_frame, orient=tk.VERTICAL, command=self.canvas.yview)
        self.scrollbar_y.pack(side=tk.RIGHT, fill=tk.Y)
        self.scrollbar_x = tk.Scrollbar(self.texture_frame, orient=tk.HORIZONTAL, command=self.canvas.xview)
        self.scrollbar_x.pack(side=tk.BOTTOM, fill=tk.X)

        self.canvas.configure(yscrollcommand=self.scrollbar_y.set, xscrollcommand=self.scrollbar_x.set)
        self.canvas.bind('<Configure>', lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))

        # Bind tree selection event to show_details method
        self.tree.bind("<<TreeviewSelect>>", self.show_details)

    def open_file(self):
        file_path = filedialog.askopenfilename(
            title="Open HNK File",
            filetypes=(("HNK files", "*.hnk"), ("All files", "*.*"))
        )
        if not file_path:
            return

        self.current_file = file_path
        self.root.title(f"Hunkfile Viewer - {file_path.split('/')[-1]}")

        try:
            parsed_records = self.read_hunkfile(file_path)
            self.populate_tree(parsed_records)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to read or parse HNK file:\n{str(e)}")

    def read_hunkfile(self, filename):
        """Reads the HNK file and parses its basic record structure."""
        records = []
        with open(filename, 'rb') as fp:
            while True:
                record_size_bytes = fp.read(4)
                if not record_size_bytes:
                    break
                record_type_bytes = fp.read(4)
                if not record_type_bytes:
                    messagebox.showwarning("Warning", "Malformed HNK file: Unexpected EOF while reading record type.")
                    break

                record_size = struct.unpack('<I', record_size_bytes)[0]
                record_type = struct.unpack('<I', record_type_bytes)[0]

                data = fp.read(record_size)
                if len(data) < record_size:
                    messagebox.showwarning("Warning", f"Malformed HNK file: Expected {record_size} bytes for record type 0x{record_type:X}, got {len(data)}.")
                    break
                
                records.append((record_size, record_type, data, fp.tell()))
        return records

    def parse_filename_header(self, data):
        """Parses a FILENAME record (type 0x40071)."""
        try:
            values = struct.unpack('<hhhhh', data[:10])
            folder_length = values[3]
            filename_length = values[4]

            folder_offset = 10
            filename_offset = 10 + folder_length

            folder = data[folder_offset : folder_offset + folder_length].decode('utf-8', errors='ignore').rstrip('\x00')
            filename = data[filename_offset : filename_offset + filename_length].decode('utf-8', errors='ignore').rstrip('\x00')

            return folder, filename
        except struct.error:
            return "ErrorParsing", "ErrorParsing"
        except IndexError:
            return "ErrorParsing", "ErrorParsingData"

    def parse_41150_header(self, data):
        """Parses a texture header record (type 0x41150)."""
        OFFSET_WIDTH = 0x0C  # Wii
        OFFSET_HEIGHT = 0x0E  # Wii
        HEADER_MIN_LENGTH = 0x16

        if len(data) >= HEADER_MIN_LENGTH:
            width = struct.unpack('>H', data[OFFSET_WIDTH:OFFSET_WIDTH+2])[0]  # Changed to big-endian
            height = struct.unpack('>H', data[OFFSET_HEIGHT:OFFSET_HEIGHT+2])[0]  # Changed to big-endian
            
            # Always return CRMP format for Wii textures
            texture_format = "CRMP"
            
            return width, height, texture_format
        
        return 0, 0, "CRMP"

    def decode_crmp_texture(self, data, width, height):
        """Decodes CRMP texture using WiiTextureDecoder."""
        try:
            image = np.zeros((height, width, 4), dtype=np.uint8)
            blocks_wide = (width + 7) // 8
            
            for block_idx in range(len(data) // 32):
                block_y = block_idx // blocks_wide
                block_x = block_idx % blocks_wide
                block_data = data[block_idx*32 : block_idx*32+32]
                
                # 4 subblocks 4x4 in each 8x8 block
                for i, (dx, dy) in enumerate([(0,0), (4,0), (0,4), (4,4)]):
                    x = block_x * 8 + dx
                    y = block_y * 8 + dy
                    subblock = block_data[i*8 : i*8+8]
                    WiiTextureDecoder.decode_block(subblock, x, y, image, width, height)
            
            return Image.fromarray(image, "RGBA")
        except Exception as e:
            print(f"Error decoding CRMP texture: {e}")
            return None

    def show_texture(self, texture_data, width, height, texture_format):
        """Displays the texture in the canvas using CRMP decoder."""
        self.canvas.delete("all")

        if width == 0 or height == 0:
            self.canvas.create_text(50, 50, text="Invalid texture dimensions (0x0).", fill="orange")
            return False

        try:
            # Decode CRMP texture
            img = self.decode_crmp_texture(texture_data, width, height)
            if img is None:
                raise ValueError("Failed to decode CRMP texture")

            # Resize image to fit canvas if it's too large, maintaining aspect ratio
            canvas_width = self.texture_frame.winfo_width() - 20
            canvas_height = self.texture_frame.winfo_height() - 20

            img_display_width, img_display_height = img.width, img.height
            if img.width > canvas_width or img.height > canvas_height:
                ratio = min(canvas_width / img.width, canvas_height / img.height)
                if ratio > 0:
                    img_display_width = int(img.width * ratio)
                    img_display_height = int(img.height * ratio)
                    if img_display_width > 0 and img_display_height > 0:
                         img = img.resize((img_display_width, img_display_height), Image.Resampling.LANCZOS)

            # Create PhotoImage and display on canvas
            self.texture_image = ImageTk.PhotoImage(img)
            self.canvas.create_image(0, 0, anchor=tk.NW, image=self.texture_image)
            self.canvas.config(scrollregion=self.canvas.bbox("all"))
            return True

        except Exception as e:
            error_message = f"Failed to display texture ({width}x{height}, {texture_format}):\n{str(e)}"
            self.canvas.create_text(10, 10, text=error_message, fill="red", anchor=tk.NW, width=self.canvas.winfo_width() - 20)
            return False

    def populate_tree(self, parsed_records):
        """Populates the Treeview with records from the HNK file."""
        self.tree.delete(*self.tree.get_children())
        self.records = parsed_records
        self.canvas.delete("all")
        self.details.delete(1.0, tk.END)
        self.textures.clear()

        current_texture_id_awaiting_data = None

        for i, (record_size, record_type, record_data, record_pos) in enumerate(self.records):
            details_summary = ""

            if record_type == RECORD_TYPE_FILENAME:
                folder, filename = self.parse_filename_header(record_data)
                details_summary = f"File: {filename}"
                if folder:
                    details_summary += f" (in {folder})"

            elif record_type == RECORD_TYPE_TEXTURE_HEADER:
                width, height, texture_format = self.parse_41150_header(record_data)
                details_summary = f"Texture Header: {width}x{height} ({texture_format})"
                
                current_texture_id_awaiting_data = f"texture_{len(self.textures)}"
                self.textures[current_texture_id_awaiting_data] = {
                    'width': width,
                    'height': height,
                    'format': texture_format,
                    'header_pos': record_pos,
                    'data': None,
                    'data_pos': None
                }
            elif record_type == RECORD_TYPE_TEXTURE_DATA:
                details_summary = "Texture Data"
                if current_texture_id_awaiting_data and current_texture_id_awaiting_data in self.textures:
                    self.textures[current_texture_id_awaiting_data]['data'] = record_data
                    self.textures[current_texture_id_awaiting_data]['data_pos'] = record_pos
                    tex_info = self.textures[current_texture_id_awaiting_data]
                    details_summary += f" ( {tex_info['width']}x{tex_info['height']} {tex_info['format']})"
                    current_texture_id_awaiting_data = None
                else:
                    details_summary += " (Orphaned? No preceding header)"

            self.tree.insert(
                "", "end", iid=str(i),
                values=(f"0x{record_type:08X}", f"{record_size} bytes", details_summary),
                tags=(f"pos_{record_pos}", f"type_{record_type}")
            )

    def show_details(self, event):
        """Displays detailed information about the selected record in the tree."""
        selection = self.tree.selection()
        if not selection:
            return
        
        selected_item_iid = selection[0]
        try:
            record_index = int(selected_item_iid)
            _record_size, record_type, record_data, record_pos = self.records[record_index]
        except (ValueError, IndexError):
            self.details.delete(1.0, tk.END)
            self.details.insert(tk.END, "Error: Could not retrieve record details.")
            return

        self.details.delete(1.0, tk.END)
        self.details.insert(tk.END, f"Record Type: 0x{record_type:08X}\n")
        self.details.insert(tk.END, f"Record Size: {_record_size} bytes\n")
        self.details.insert(tk.END, f"Record Position (end in file): {record_pos} bytes\n")

        if record_type == RECORD_TYPE_FILENAME:
            folder, filename = self.parse_filename_header(record_data)
            self.details.insert(tk.END, f"Parsed Folder: {folder}\n")
            self.details.insert(tk.END, f"Parsed Filename: {filename}\n")

        elif record_type == RECORD_TYPE_TEXTURE_HEADER:
            width, height, texture_format = self.parse_41150_header(record_data)
            self.details.insert(tk.END, f"Texture Dimensions: {width}x{height}\n")
            self.details.insert(tk.END, f"Detected Format: {texture_format}\n")
            for tex_id, tex_meta in self.textures.items():
                if tex_meta['header_pos'] == record_pos and tex_meta['data'] is not None:
                    self.details.insert(tk.END, "Associated texture data found.\n")
                    if tex_meta['width'] > 0 and tex_meta['height'] > 0:
                        self.show_texture(
                            tex_meta['data'],
                            tex_meta['width'],
                            tex_meta['height'],
                            tex_meta['format']
                        )
                    break

        elif record_type == RECORD_TYPE_TEXTURE_DATA:
            self.details.insert(tk.END, "This is raw texture data.\n")
            found_texture_for_data = False
            for tex_id, tex_meta in self.textures.items():
                if tex_meta.get('data_pos') == record_pos:
                    self.details.insert(tk.END, f"Associated with Texture Header:\n")
                    self.details.insert(tk.END, f"  Dimensions: {tex_meta['width']}x{tex_meta['height']}\n")
                    self.details.insert(tk.END, f"  Format: {tex_meta['format']}\n")
                    
                    if tex_meta['width'] > 0 and tex_meta['height'] > 0 and tex_meta['data']:
                        self.show_texture(
                            tex_meta['data'],
                            tex_meta['width'],
                            tex_meta['height'],
                            tex_meta['format']
                        )
                    else:
                        self.canvas.delete("all")
                        self.canvas.create_text(50,50, text="Texture data available, but metadata (W/H) is invalid or data is missing.", fill="orange")
                    found_texture_for_data = True
                    break
            if not found_texture_for_data:
                self.canvas.delete("all")
                self.canvas.create_text(50,50, text="Texture data found, but no associated header information in current parse.", fill="orange")

        # Display a hex dump of the first few bytes of the record data
        self.details.insert(tk.END, "\nHex Data (first 64 bytes or less):\n")
        max_hex_bytes = min(len(record_data), 64)
        hex_lines = []
        for i in range(0, max_hex_bytes, 16):
            chunk = record_data[i:i+16]
            hex_str = ' '.join(f"{b:02X}" for b in chunk)
            ascii_str = ''.join(chr(b) if 32 <= b <= 126 else '.' for b in chunk)
            hex_lines.append(f"{i:04X}: {hex_str:<48} {ascii_str}")
        
        self.details.insert(tk.END, "\n".join(hex_lines))
        if len(record_data) > max_hex_bytes:
            self.details.insert(tk.END, "\n...")

if __name__ == "__main__":
    root = tk.Tk()
    app = HunkfileViewer(root)
    root.geometry("1200x800")
    root.mainloop()
