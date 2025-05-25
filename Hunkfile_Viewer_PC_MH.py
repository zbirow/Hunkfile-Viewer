import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from tkinter.scrolledtext import ScrolledText
import struct
import io
from PIL import Image, ImageTk

# Define record type constants for better readability and maintainability
RECORD_TYPE_FILENAME = 0x40071
RECORD_TYPE_TEXTURE_HEADER = 0x41150
RECORD_TYPE_TEXTURE_DATA = 0x40151 # Assuming this is the texture data type

class HunkfileViewer:
    def __init__(self, root):
        self.root = root
        self.root.title("Hunkfile Viewer")

        self.records = []  # Stores all parsed records from the HNK file
        self.current_file = None  # Path to the currently opened HNK file
        self.texture_image = None  # Holds the PhotoImage object for the texture preview
        # self.texture_window = None # This attribute was declared but not used. Removed.

        self.textures = {} # Dictionary to store texture metadata and data, keyed by a generated ID

        self.create_widgets()
        self.context_menu = tk.Menu(self.root, tearoff=0)
        self.context_menu.add_command(label="Export to .dat", command=self.export_selected_record)

    def create_widgets(self):
        # Main container with a sash (PanedWindow) for resizable panels
        main_panel = tk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        main_panel.pack(fill=tk.BOTH, expand=True)

        # Left panel - for record tree and action buttons
        left_panel = tk.Frame(main_panel, width=300) # Initial width, resizable
        main_panel.add(left_panel)

        # Right panel - for record details and texture preview
        # This is also a PanedWindow to allow resizing between details and preview
        right_panel = tk.PanedWindow(main_panel, orient=tk.VERTICAL)
        main_panel.add(right_panel)

        # Button frame within the left panel
        button_frame = tk.Frame(left_panel)
        button_frame.pack(fill=tk.X, padx=5, pady=5)

        open_button = tk.Button(button_frame, text="Open HNK File", command=self.open_file)
        open_button.pack(side=tk.LEFT, expand=True) # Expand to fill available width

        # Treeview to display HNK file records
        self.tree = ttk.Treeview(left_panel, columns=("Type", "Size", "Details"), show="headings")
        self.tree.heading("Type", text="Record Type")
        self.tree.heading("Size", text="Record Size")
        self.tree.heading("Details", text="Details")
        self.tree.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Bind right-click event to show context menu
        self.tree.bind("<Button-3>", self.show_context_menu)

        # Details panel (ScrolledText) within the right panel
        details_frame = tk.Frame(right_panel) # Frame to contain the ScrolledText
        right_panel.add(details_frame) # Add to the PanedWindow

        self.details = ScrolledText(details_frame, height=10) # Initial height, resizable
        self.details.pack(fill=tk.BOTH, expand=True)

        # Texture preview panel (LabelFrame with Canvas) within the right panel
        self.texture_frame = tk.LabelFrame(right_panel, text="Texture Preview", height=400) # Initial height
        right_panel.add(self.texture_frame) # Add to the PanedWindow

        self.canvas = tk.Canvas(self.texture_frame, bg='white')
        self.canvas.pack(fill=tk.BOTH, expand=True)

        # Scrollbars for the texture preview canvas
        self.scrollbar_y = tk.Scrollbar(self.texture_frame, orient=tk.VERTICAL, command=self.canvas.yview)
        self.scrollbar_y.pack(side=tk.RIGHT, fill=tk.Y)
        self.scrollbar_x = tk.Scrollbar(self.texture_frame, orient=tk.HORIZONTAL, command=self.canvas.xview)
        self.scrollbar_x.pack(side=tk.BOTTOM, fill=tk.X)

        self.canvas.configure(yscrollcommand=self.scrollbar_y.set, xscrollcommand=self.scrollbar_x.set)
        # Update scrollregion when canvas size changes (e.g., due to window resize or image loading)
        self.canvas.bind('<Configure>', lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))

        # Bind tree selection event to show_details method
        self.tree.bind("<<TreeviewSelect>>", self.show_details)


    def show_context_menu(self, event):
        """Show context menu on right-click"""
        item = self.tree.identify_row(event.y)
        if item:
            self.tree.selection_set(item)
            self.context_menu.post(event.x_root, event.y_root)

    def export_selected_record(self):
        """Export selected record data to a .dat file"""
        selection = self.tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "No record selected for export")
            return
            
        selected_item_iid = selection[0]
        try:
            record_index = int(selected_item_iid)
            _record_size, _record_type, record_data, _record_pos = self.records[record_index]
        except (ValueError, IndexError):
            messagebox.showerror("Error", "Could not retrieve record data for export")
            return

        # Ask user for output file path
        default_filename = f"record_{record_index:04d}.dat"
        file_path = filedialog.asksaveasfilename(
            title="Export Record Data",
            initialfile=default_filename,
            filetypes=(("DAT files", "*.dat"), ("All files", "*.*")),
            defaultextension=".dat"
        )
        
        if not file_path:  # User cancelled
            return
            
        try:
            with open(file_path, 'wb') as f:
                f.write(record_data)
            messagebox.showinfo("Success", f"Record data successfully exported to:\n{file_path}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to export record data:\n{str(e)}")        

    def open_file(self):
        file_path = filedialog.askopenfilename(
            title="Open HNK File",
            filetypes=(("HNK files", "*.hnk"), ("All files", "*.*"))
        )
        if not file_path: # User cancelled the dialog
            return

        self.current_file = file_path
        self.root.title(f"Hunkfile Viewer - {file_path.split('/')[-1]}") # Update window title

        try:
            parsed_records = self.read_hunkfile(file_path)
            self.populate_tree(parsed_records)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to read or parse HNK file:\n{str(e)}")

    def read_hunkfile(self, filename):
        """
        Reads the HNK file and parses its basic record structure.
        Each record is expected to have a 4-byte size, a 4-byte type, and then data.
        """
        records = []
        with open(filename, 'rb') as fp:
            while True:
                # Read record size (4 bytes, unsigned int)
                record_size_bytes = fp.read(4)
                if not record_size_bytes: # End of file
                    break
                # Read record type (4 bytes, unsigned int)
                record_type_bytes = fp.read(4)
                if not record_type_bytes: # Should not happen if size was read, indicates malformed file
                    messagebox.showwarning("Warning", "Malformed HNK file: Unexpected EOF while reading record type.")
                    break

                record_size = struct.unpack('<I', record_size_bytes)[0] # Assuming little-endian, common for many formats
                record_type = struct.unpack('<I', record_type_bytes)[0] # Assuming little-endian

                # Read the actual record data based on record_size
                data = fp.read(record_size)
                if len(data) < record_size: # Check if enough data was read
                    messagebox.showwarning("Warning", f"Malformed HNK file: Expected {record_size} bytes for record type 0x{record_type:X}, got {len(data)}.")
                    break
                
                # Store record size, type, data, and current file position (end of record)
                records.append((record_size, record_type, data, fp.tell()))
        return records

    def parse_filename_header(self, data):
        """
        Parses a FILENAME record (type 0x40071).
        The structure seems to be: 5 shorts (10 bytes), then folder string, then filename string.
        """
        try:
            # h = short (2 bytes)
            values = struct.unpack('<hhhhh', data[:10]) # Assuming little-endian
            # values[0], values[1], values[2] are unknown/unused here
            folder_length = values[3]
            filename_length = values[4]

            folder_offset = 10
            filename_offset = 10 + folder_length

            folder = data[folder_offset : folder_offset + folder_length].decode('utf-8', errors='ignore').rstrip('\x00')
            filename = data[filename_offset : filename_offset + filename_length].decode('utf-8', errors='ignore').rstrip('\x00')

            return folder, filename
        except struct.error:
            # Not enough data for the header
            return "ErrorParsing", "ErrorParsing"
        except IndexError:
            # Data shorter than expected based on lengths
            return "ErrorParsing", "ErrorParsingData"


    def parse_41150_header(self, data):
        """
        Parses a texture header record (type 0x41150).
        Extracts width, height, and attempts to determine texture format.
        """
        # Offsets for width and height within this record type
        OFFSET_WIDTH = 0x0C
        OFFSET_HEIGHT = 0x0E
        HEADER_MIN_LENGTH = 0x10 # Minimum length to safely read up to height

        if len(data) >= HEADER_MIN_LENGTH:
            width = struct.unpack('<H', data[OFFSET_WIDTH:OFFSET_WIDTH+2])[0]   # little-endian
            height = struct.unpack('<H', data[OFFSET_HEIGHT:OFFSET_HEIGHT+2])[0] # little-endian

            texture_format = "DXT1"  # Default format if not otherwise determined
            
            # Check for format marker bytes at the beginning of the record data
            if len(data) >= 0x02: # Ensure at least 2 bytes exist for the marker
                format_marker = data[0x00:0x02]
                # These markers seem specific to the HNK format or the tools that create them.
                # It would be good to document their origin if known.
                if format_marker == b'\xF9\x3D':
                    texture_format = "DXT1"
                elif format_marker == b'\xD3\x3A':
                    texture_format = "DXT5"
                elif format_marker == b'\x6F\x74':  # Potentially 'ot' for 'other' -> R8G8B8A8
                    texture_format = "R8G8B8A8"
                else:
                    # print(f"Debug: Unknown format marker: {format_marker.hex(' ')}") # For debugging
                    pass # Keep default DXT1 or handle as an unknown format
            
            # print(f"Debug: Detected texture: {width}x{height} {texture_format}") # For debugging
            return width, height, texture_format
        
        # If data is too short for a valid header, return default/zero values
        return 0, 0, "DXT1"

    def create_dds_header(self, width, height, texture_format, mip_count=0):
        """
        Creates a DDS (DirectDraw Surface) file header.
        This header allows PIL/Pillow to interpret the raw texture data.
        Reference: https://docs.microsoft.com/en-us/windows/win32/direct3d9/dds-header
        """
        header = bytearray(128) # DDS header is 128 bytes
        
        # dwMagic: "DDS " (4 bytes)
        header[0:4] = b"DDS "
        
        # DDS_HEADER structure (124 bytes)
        # dwSize: Size of structure (124 bytes)
        header[4:8] = (124).to_bytes(4, "little")
        
        # dwFlags: Flags to indicate valid fields (DDSD_CAPS | DDSD_HEIGHT | DDSD_WIDTH | DDSD_PIXELFORMAT)
        flags = 0x1  # DDSD_CAPS
        flags |= 0x2 # DDSD_HEIGHT
        flags |= 0x4 # DDSD_WIDTH
        flags |= 0x1000 # DDSD_PIXELFORMAT
        
        if texture_format in ["DXT1", "DXT5"]:
            flags |= 0x80000  # DDSD_LINEARSIZE: For compressed formats
            linear_size = self.calculate_compressed_size(width, height, texture_format)
            pitch_or_linear_size_value = linear_size
        else:  # R8G8B8A8 (uncompressed)
            flags |= 0x8      # DDSD_PITCH: For uncompressed formats, pitch is width * bytes_per_pixel
            pitch_or_linear_size_value = width * 4  # 4 bytes per pixel (R8G8B8A8)
            
        if mip_count > 0:
            flags |= 0x20000 # DDSD_MIPMAPCOUNT

        header[8:12] = flags.to_bytes(4, "little")          # dwFlags
        header[12:16] = height.to_bytes(4, "little")        # dwHeight
        header[16:20] = width.to_bytes(4, "little")         # dwWidth
        header[20:24] = pitch_or_linear_size_value.to_bytes(4, "little") # dwPitchOrLinearSize
        header[24:28] = (0).to_bytes(4, "little")           # dwDepth (if 3D texture)
        header[28:32] = mip_count.to_bytes(4, "little")     # dwMipMapCount
        # header[32:76] are dwReserved1[11] (44 bytes), set to 0
        
        # DDS_PIXELFORMAT structure (32 bytes total, starts at offset 76)
        header[76:80] = (32).to_bytes(4, "little") # dwSize of DDS_PIXELFORMAT
        
        if texture_format in ["DXT1", "DXT5"]:
            header[80:84] = (0x4).to_bytes(4, "little")  # dwFlags: DDPF_FOURCC
            header[84:88] = texture_format.encode('ascii') # dwFourCC: "DXT1" or "DXT5"
            # dwRGBBitCount, dwRBitMask, dwGBitMask, dwBBitMask, dwABitMask are 0 for DXTn
        elif texture_format == "R8G8B8A8":
            header[80:84] = (0x41).to_bytes(4, "little") # dwFlags: DDPF_ALPHAPIXELS | DDPF_RGB
            # dwFourCC is 0 for R8G8B8A8
            header[88:92] = (32).to_bytes(4, "little")            # dwRGBBitCount (32 bpp)
            header[92:96] = (0x00FF0000).to_bytes(4, "little")    # dwRBitMask
            header[96:100] = (0x0000FF00).to_bytes(4, "little")   # dwGBitMask
            header[100:104] = (0x000000FF).to_bytes(4, "little")  # dwBBitMask
            header[104:108] = (0xFF000000).to_bytes(4, "little")  # dwABitMask
        else:
            # Should not happen if texture_format is validated
            raise ValueError(f"Unsupported texture format for DDS header: {texture_format}")

        # dwCaps: Surface capabilities
        caps1 = 0x1000  # DDSCAPS_TEXTURE
        if mip_count > 0:
            caps1 |= 0x400008 # DDSCAPS_MIPMAP | DDSCAPS_COMPLEX
        header[108:112] = caps1.to_bytes(4, "little") # dwCaps
        # header[112:116] is dwCaps2, header[116:120] is dwCaps3, header[120:124] is dwCaps4
        # header[124:128] is dwReserved2
        # All these are usually 0 for simple 2D textures.
        
        return header

    def calculate_compressed_size(self, width, height, texture_format):
        """Calculates the size of compressed texture data (DXT1, DXT5)."""
        # DXT1 uses 8 bytes per 4x4 block (0.5 bytes per pixel)
        # DXT5 uses 16 bytes per 4x4 block (1 byte per pixel)
        block_size = 8 if texture_format == "DXT1" else 16
        # Calculate number of blocks, rounding up
        num_blocks_wide = max(1, (width + 3) // 4)
        num_blocks_high = max(1, (height + 3) // 4)
        return num_blocks_wide * num_blocks_high * block_size

    def show_texture(self, texture_data, width, height, texture_format):
        """
        Displays the texture in the canvas.
        It constructs a DDS file in memory and uses PIL to load it.
        """
        self.canvas.delete("all") # Clear previous texture

        if width == 0 or height == 0:
            self.canvas.create_text(50, 50, text="Invalid texture dimensions (0x0).", fill="orange")
            return False

        try:
            # Create DDS header based on texture properties
            dds_header = self.create_dds_header(width, height, texture_format)

            # Combine header with the raw texture data
            dds_data_in_memory = dds_header + texture_data

            # Use BytesIO to treat the byte array as a file-like object
            with io.BytesIO(dds_data_in_memory) as dds_file_stream:
                img = Image.open(dds_file_stream)
                # Ensure image is in RGBA format for consistent display with Tkinter
                img = img.convert("RGBA")

                # Resize image to fit canvas if it's too large, maintaining aspect ratio
                canvas_width = self.texture_frame.winfo_width() - 20 # Subtract some padding
                canvas_height = self.texture_frame.winfo_height() - 20

                img_display_width, img_display_height = img.width, img.height
                if img.width > canvas_width or img.height > canvas_height:
                    ratio = min(canvas_width / img.width, canvas_height / img.height)
                    if ratio > 0: # Ensure ratio is positive
                        img_display_width = int(img.width * ratio)
                        img_display_height = int(img.height * ratio)
                        # Ensure minimum dimensions for resizing
                        if img_display_width > 0 and img_display_height > 0:
                             img = img.resize((img_display_width, img_display_height), Image.Resampling.LANCZOS)

                # Create PhotoImage and display on canvas
                self.texture_image = ImageTk.PhotoImage(img)
                self.canvas.create_image(0, 0, anchor=tk.NW, image=self.texture_image)
                # Update scrollregion to encompass the new image
                self.canvas.config(scrollregion=self.canvas.bbox("all"))
                return True

        except Exception as e:
            # print(f"Error displaying texture: {e}") # For debugging
            error_message = f"Failed to display texture ({width}x{height}, {texture_format}):\n{str(e)}"
            self.canvas.create_text(10, 10, text=error_message, fill="red", anchor=tk.NW, width=self.canvas.winfo_width() - 20)
            return False

    def populate_tree(self, parsed_records):
        """Populates the Treeview with records from the HNK file."""
        self.tree.delete(*self.tree.get_children()) # Clear existing items
        self.records = parsed_records # Store the full list of records
        self.canvas.delete("all") # Clear texture preview
        self.details.delete(1.0, tk.END) # Clear details view
        self.textures.clear() # Clear previously loaded texture metadata

        # This temporary variable helps link a texture header with its subsequent data record.
        # It assumes that texture data (0x40151) immediately follows its header (0x41150).
        current_texture_id_awaiting_data = None

        for i, (record_size, record_type, record_data, record_pos) in enumerate(self.records):
            details_summary = "" # Short summary for the tree view

            if record_type == RECORD_TYPE_FILENAME: # Filename record
                folder, filename = self.parse_filename_header(record_data)
                details_summary = f"File: {filename}"
                if folder:
                    details_summary += f" (in {folder})"

            elif record_type == RECORD_TYPE_TEXTURE_HEADER: # Texture header record
                width, height, texture_format = self.parse_41150_header(record_data)
                details_summary = f"Texture Header: {width}x{height} ({texture_format})"
                
                # Generate a unique ID for this texture and store its metadata
                current_texture_id_awaiting_data = f"texture_{len(self.textures)}"
                self.textures[current_texture_id_awaiting_data] = {
                    'width': width,
                    'height': height,
                    'format': texture_format,
                    'header_pos': record_pos, # Store position of the header record
                    'data': None, # Data will be filled by the next relevant record
                    'data_pos': None
                }
            elif record_type == RECORD_TYPE_TEXTURE_DATA: # Texture data record
                details_summary = "Texture Data"
                if current_texture_id_awaiting_data and current_texture_id_awaiting_data in self.textures:
                    # Link this data to the most recent texture header
                    self.textures[current_texture_id_awaiting_data]['data'] = record_data
                    self.textures[current_texture_id_awaiting_data]['data_pos'] = record_pos
                    # Add size to details for clarity if texture is now complete
                    tex_info = self.textures[current_texture_id_awaiting_data]
                    details_summary += f" ( {tex_info['width']}x{tex_info['height']} {tex_info['format']})"
                    current_texture_id_awaiting_data = None # Reset, as data has been found
                else:
                    details_summary += " (Orphaned? No preceding header)"


            # Insert item into the tree. Use `i` as a unique item ID (iid).
            # Tags store the record position and type for later retrieval.
            self.tree.insert(
                "", "end", iid=str(i), # iid must be a string
                values=(f"0x{record_type:08X}", f"{record_size} bytes", details_summary),
                tags=(f"pos_{record_pos}", f"type_{record_type}")
            )
        # self.textures = textures # No longer needed if self.textures is populated directly

    def show_details(self, event):
        """Displays detailed information about the selected record in the tree."""
        selection = self.tree.selection()
        if not selection: # No item selected
            return
        
        selected_item_iid = selection[0]
        # Retrieve the original record index from the iid
        try:
            record_index = int(selected_item_iid)
            _record_size, record_type, record_data, record_pos = self.records[record_index]
        except (ValueError, IndexError):
            self.details.delete(1.0, tk.END)
            self.details.insert(tk.END, "Error: Could not retrieve record details.")
            return

        self.details.delete(1.0, tk.END) # Clear previous details
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
            # Check if there's corresponding data and try to show it
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
            # Find which texture this data belongs to by matching its data_pos
            for tex_id, tex_meta in self.textures.items():
                if tex_meta.get('data_pos') == record_pos: # Check if 'data_pos' key exists
                    self.details.insert(tk.END, f"Associated with Texture Header:\n")
                    self.details.insert(tk.END, f"  Dimensions: {tex_meta['width']}x{tex_meta['height']}\n")
                    self.details.insert(tk.END, f"  Format: {tex_meta['format']}\n")
                    
                    if tex_meta['width'] > 0 and tex_meta['height'] > 0 and tex_meta['data']:
                        self.show_texture(
                            tex_meta['data'], # which is record_data
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
    root.geometry("1200x800") # Set a default window size
    root.mainloop()
