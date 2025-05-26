
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from tkinter.scrolledtext import ScrolledText
import struct
import io
from PIL import Image, ImageTk

# Define all record type constants
RECORD_TYPE_HUNKFILE_HEADER = 0x40070
RECORD_TYPE_FILENAME = 0x40071
RECORD_TYPE_EMPTY = 0x40072
RECORD_TYPE_ABSTRACT_HASH = 0x40002
RECORD_TYPE_STRING_TABLE = 0x4100F
RECORD_TYPE_CLANK_BODY_MAIN = 0x45100
RECORD_TYPE_CLANK_BODY_SECONDARY = 0x402100
RECORD_TYPE_CLANK_BODY_NAME = 0x43100
RECORD_TYPE_CLANK_BODY_DATA = 0x44100
RECORD_TYPE_CLANK_BODY_DATA2 = 0x404100
RECORD_TYPE_LITESCRIPT_MAIN = 0x4300c
RECORD_TYPE_LITESCRIPT_DATA = 0x4200c
RECORD_TYPE_LITESCRIPT_DATA2 = 0x4100c
RECORD_TYPE_SQUEAK_SAMPLE = 0x204090
RECORD_TYPE_TEXTURE_HEADER = 0x41150
RECORD_TYPE_TEXTURE_DATA = 0x40151
RECORD_TYPE_TEXTURE_DATA2 = 0x801151
RECORD_TYPE_RENDER_MODEL_HEADER = 0x101050
RECORD_TYPE_RENDER_MODEL_DATA = 0x40054
RECORD_TYPE_RENDER_MODEL_TABLE = 0x20055
RECORD_TYPE_ANIMATION_DATA = 0x42005
RECORD_TYPE_ANIMATION_DATA2 = 0x41005
RECORD_TYPE_RENDER_SPRITE = 0x41007
RECORD_TYPE_EFFECTS_PARAMS = 0x43112
RECORD_TYPE_FONT_DESCRIPTOR = 0x43087
RECORD_TYPE_DATA_TABLE1 = 0x43083
RECORD_TYPE_DATA_TABLE2 = 0x4008a
RECORD_TYPE_STATE_FLOW1 = 0x43088
RECORD_TYPE_STATE_FLOW2 = 0x42088
RECORD_TYPE_SQUEAK_STREAM = 0x204092
RECORD_TYPE_SQUEAK_STREAM2 = 0x201092
RECORD_TYPE_ENTITY_PLACEMENT = 0x42009
RECORD_TYPE_ENTITY_PLACEMENT2 = 0x103009
RECORD_TYPE_ENTITY_PLACEMENT_BCC = 0x101009
RECORD_TYPE_ENTITY_PLACEMENT_LEVEL = 0x102009
RECORD_TYPE_ENTITY_TEMPLATE = 0x101008

class HunkfileViewer:
    def __init__(self, root):
        self.root = root
        self.root.title("Hunkfile Viewer")

        self.records = []  # Stores all parsed records from the HNK file
        self.current_file = None  # Path to the currently opened HNK file
        self.texture_image = None  # Holds the PhotoImage object for the texture preview
        self.textures = {} # Dictionary to store texture metadata and data, keyed by a generated ID
        self.string_tables = {} # Dictionary to store string tables
        self.models = {} # Dictionary to store 3D model data
        self.animations = {} # Dictionary to store animation data
        self.entities = {} # Dictionary to store entity data

        self.create_widgets()
        self.context_menu = tk.Menu(self.root, tearoff=0)
        self.context_menu.add_command(label="Export to .dat", command=self.export_selected_record)

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

        # Bind right-click event to show context menu
        self.tree.bind("<Button-3>", self.show_context_menu)

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
        self.root.title(f"Hunkfile Viewer - {file_path.split('/')[-1]}")

        try:
            parsed_records = self.read_hunkfile(file_path)
            self.populate_tree(parsed_records)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to read or parse HNK file:\n{str(e)}")

    def read_hunkfile(self, filename):
        """Reads the HNK file and parses its record structure."""
        records = []
        with open(filename, 'rb') as fp:
            while True:
                # Read record size (4 bytes, unsigned int)
                record_size_bytes = fp.read(4)
                if not record_size_bytes: # End of file
                    break
                # Read record type (4 bytes, unsigned int)
                record_type_bytes = fp.read(4)
                if not record_type_bytes:
                    messagebox.showwarning("Warning", "Malformed HNK file: Unexpected EOF while reading record type.")
                    break

                record_size = struct.unpack('<I', record_size_bytes)[0]
                record_type = struct.unpack('<I', record_type_bytes)[0]

                # Read the actual record data
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

    def parse_string_table(self, data):
        """Parses a string table record (type 0x4100F)."""
        try:
            # First 4 bytes might be the count of strings
            string_count = struct.unpack('<I', data[:4])[0]
            strings = []
            offset = 4
            
            for _ in range(string_count):
                # Strings are null-terminated
                end = data.find(b'\x00', offset)
                if end == -1:
                    break
                string = data[offset:end].decode('utf-8', errors='ignore')
                strings.append(string)
                offset = end + 1
            
            return strings
        except Exception as e:
            return [f"Error parsing string table: {str(e)}"]

    def parse_texture_header(self, data):
        """Parses a texture header record (type 0x41150)."""
        OFFSET_WIDTH = 0x0C
        OFFSET_HEIGHT = 0x0E
        HEADER_MIN_LENGTH = 0x10

        if len(data) >= HEADER_MIN_LENGTH:
            width = struct.unpack('<H', data[OFFSET_WIDTH:OFFSET_WIDTH+2])[0]
            height = struct.unpack('<H', data[OFFSET_HEIGHT:OFFSET_HEIGHT+2])[0]

            texture_format = "DXT1"  # Default format
            
            if len(data) >= 0x02:
                format_marker = data[0x00:0x02]
                if format_marker == b'\xF9\x3D':
                    texture_format = "DXT1"
                elif format_marker == b'\xD3\x3A':
                    texture_format = "DXT5"
                elif format_marker == b'\x6F\x74':
                    texture_format = "R8G8B8A8"
            
            return width, height, texture_format
        
        return 0, 0, "DXT1"

    def parse_model_header(self, data):
        """Parses a render model header (type 0x101050)."""
        try:
            # Example parsing - actual structure may vary
            vertex_count = struct.unpack('<I', data[0:4])[0]
            face_count = struct.unpack('<I', data[4:8])[0]
            return vertex_count, face_count
        except:
            return 0, 0

    def parse_animation_data(self, data):
        """Parses animation data (types 0x42005, 0x41005)."""
        try:
            # Example parsing - actual structure may vary
            frame_count = struct.unpack('<I', data[0:4])[0]
            duration = struct.unpack('<f', data[4:8])[0]
            return frame_count, duration
        except:
            return 0, 0.0

    def parse_entity_data(self, data):
        """Parses entity placement data (types 0x42009, etc.)."""
        try:
            # Example parsing - actual structure may vary
            x, y, z = struct.unpack('<fff', data[0:12])
            return x, y, z
        except:
            return 0.0, 0.0, 0.0

    def create_dds_header(self, width, height, texture_format, mip_count=0):
        """Creates a DDS file header."""
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
        """Calculates the size of compressed texture data."""
        block_size = 8 if texture_format == "DXT1" else 16
        num_blocks_wide = max(1, (width + 3) // 4)
        num_blocks_high = max(1, (height + 3) // 4)
        return num_blocks_wide * num_blocks_high * block_size

    def show_texture(self, texture_data, width, height, texture_format):
        """Displays the texture in the canvas."""
        self.canvas.delete("all")

        if width == 0 or height == 0:
            self.canvas.create_text(50, 50, text="Invalid texture dimensions (0x0).", fill="orange")
            return False

        try:
            dds_header = self.create_dds_header(width, height, texture_format)
            dds_data_in_memory = dds_header + texture_data

            with io.BytesIO(dds_data_in_memory) as dds_file_stream:
                img = Image.open(dds_file_stream)
                img = img.convert("RGBA")

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
        self.string_tables.clear()
        self.models.clear()
        self.animations.clear()
        self.entities.clear()

        current_texture_id_awaiting_data = None
        current_model_id_awaiting_data = None
        current_animation_id_awaiting_data = None
        current_entity_id_awaiting_data = None

        for i, (record_size, record_type, record_data, record_pos) in enumerate(self.records):
            details_summary = ""

            if record_type == RECORD_TYPE_HUNKFILE_HEADER:
                details_summary = "Hunkfile Header"
                
            elif record_type == RECORD_TYPE_FILENAME:
                folder, filename = self.parse_filename_header(record_data)
                details_summary = f"File: {filename}"
                if folder:
                    details_summary += f" (in {folder})"

            elif record_type == RECORD_TYPE_EMPTY:
                details_summary = "Empty Record"
                
            elif record_type == RECORD_TYPE_ABSTRACT_HASH:
                details_summary = "Abstract Hash Identifier"
                
            elif record_type == RECORD_TYPE_STRING_TABLE:
                strings = self.parse_string_table(record_data)
                table_id = f"string_table_{len(self.string_tables)}"
                self.string_tables[table_id] = strings
                details_summary = f"String Table ({len(strings)} strings)"
                
            elif record_type == RECORD_TYPE_TEXTURE_HEADER:
                width, height, texture_format = self.parse_texture_header(record_data)
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
                
            elif record_type in [RECORD_TYPE_TEXTURE_DATA, RECORD_TYPE_TEXTURE_DATA2]:
                details_summary = "Texture Data"
                if current_texture_id_awaiting_data and current_texture_id_awaiting_data in self.textures:
                    self.textures[current_texture_id_awaiting_data]['data'] = record_data
                    self.textures[current_texture_id_awaiting_data]['data_pos'] = record_pos
                    tex_info = self.textures[current_texture_id_awaiting_data]
                    details_summary += f" ( {tex_info['width']}x{tex_info['height']} {tex_info['format']})"
                    current_texture_id_awaiting_data = None
                else:
                    details_summary += " (Orphaned? No preceding header)"

            elif record_type == RECORD_TYPE_RENDER_MODEL_HEADER:
                vertex_count, face_count = self.parse_model_header(record_data)
                details_summary = f"Render Model Header: {vertex_count} vertices, {face_count} faces"
                current_model_id_awaiting_data = f"model_{len(self.models)}"
                self.models[current_model_id_awaiting_data] = {
                    'vertex_count': vertex_count,
                    'face_count': face_count,
                    'header_pos': record_pos,
                    'data': None,
                    'data_pos': None
                }
                
            elif record_type in [RECORD_TYPE_RENDER_MODEL_DATA, RECORD_TYPE_RENDER_MODEL_TABLE]:
                details_summary = "Render Model Data"
                if current_model_id_awaiting_data and current_model_id_awaiting_data in self.models:
                    self.models[current_model_id_awaiting_data]['data'] = record_data
                    self.models[current_model_id_awaiting_data]['data_pos'] = record_pos
                    model_info = self.models[current_model_id_awaiting_data]
                    details_summary += f" ({model_info['vertex_count']} vertices)"
                    current_model_id_awaiting_data = None
                else:
                    details_summary += " (Orphaned? No preceding header)"
                    
            elif record_type in [RECORD_TYPE_ANIMATION_DATA, RECORD_TYPE_ANIMATION_DATA2]:
                frame_count, duration = self.parse_animation_data(record_data)
                details_summary = f"Animation Data: {frame_count} frames, {duration:.2f}s"
                current_animation_id_awaiting_data = f"animation_{len(self.animations)}"
                self.animations[current_animation_id_awaiting_data] = {
                    'frame_count': frame_count,
                    'duration': duration,
                    'data': record_data,
                    'data_pos': record_pos
                }
                
            elif record_type == RECORD_TYPE_RENDER_SPRITE:
                details_summary = "Render Sprite Data"
                
            elif record_type == RECORD_TYPE_EFFECTS_PARAMS:
                details_summary = "Effects Parameters"
                
            elif record_type == RECORD_TYPE_FONT_DESCRIPTOR:
                details_summary = "Font Descriptor"
                
            elif record_type in [RECORD_TYPE_DATA_TABLE1, RECORD_TYPE_DATA_TABLE2]:
                details_summary = "Data Table"
                
            elif record_type in [RECORD_TYPE_STATE_FLOW1, RECORD_TYPE_STATE_FLOW2]:
                details_summary = "State Flow Template"
                
            elif record_type in [RECORD_TYPE_SQUEAK_SAMPLE, RECORD_TYPE_SQUEAK_STREAM, RECORD_TYPE_SQUEAK_STREAM2]:
                details_summary = "Audio Data"
                
            elif record_type in [RECORD_TYPE_ENTITY_PLACEMENT, RECORD_TYPE_ENTITY_PLACEMENT2, 
                               RECORD_TYPE_ENTITY_PLACEMENT_BCC, RECORD_TYPE_ENTITY_PLACEMENT_LEVEL]:
                x, y, z = self.parse_entity_data(record_data)
                details_summary = f"Entity Placement: ({x:.2f}, {y:.2f}, {z:.2f})"
                current_entity_id_awaiting_data = f"entity_{len(self.entities)}"
                self.entities[current_entity_id_awaiting_data] = {
                    'x': x,
                    'y': y,
                    'z': z,
                    'data': record_data,
                    'data_pos': record_pos
                }
                
            elif record_type == RECORD_TYPE_ENTITY_TEMPLATE:
                details_summary = "Entity Template Data"
                
            else:
                details_summary = f"Unknown Record Type (0x{record_type:08X})"

            self.tree.insert(
                "", "end", iid=str(i),
                values=(f"0x{record_type:08X}", f"{record_size} bytes", details_summary),
                tags=(f"pos_{record_pos}", f"type_{record_type}")
            )

    def show_details(self, event):
        """Displays detailed information about the selected record."""
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

        elif record_type == RECORD_TYPE_STRING_TABLE:
            table_id = None
            for tid, table in self.string_tables.items():
                if any(str(record_pos) in tid or str(record_pos - _record_size) in tid):
                    table_id = tid
                    break
            
            if table_id:
                strings = self.string_tables[table_id]
                self.details.insert(tk.END, f"String Table Contents ({len(strings)} strings):\n")
                for i, s in enumerate(strings):
                    self.details.insert(tk.END, f"  {i}: {s}\n")
            else:
                self.details.insert(tk.END, "String table data not found in cache.\n")

        elif record_type == RECORD_TYPE_TEXTURE_HEADER:
            width, height, texture_format = self.parse_texture_header(record_data)
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

        elif record_type in [RECORD_TYPE_TEXTURE_DATA, RECORD_TYPE_TEXTURE_DATA2]:
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
                        self.canvas.create_text(50,50, text="Texture data available, but metadata is invalid.", fill="orange")
                    found_texture_for_data = True
                    break
            if not found_texture_for_data:
                self.canvas.delete("all")
                self.canvas.create_text(50,50, text="Texture data found, but no associated header.", fill="orange")

        elif record_type == RECORD_TYPE_RENDER_MODEL_HEADER:
            vertex_count, face_count = self.parse_model_header(record_data)
            self.details.insert(tk.END, f"Model Info: {vertex_count} vertices, {face_count} faces\n")
            
            for model_id, model_meta in self.models.items():
                if model_meta['header_pos'] == record_pos and model_meta['data'] is not None:
                    self.details.insert(tk.END, "Associated model data found.\n")
                    break

        elif record_type in [RECORD_TYPE_RENDER_MODEL_DATA, RECORD_TYPE_RENDER_MODEL_TABLE]:
            found_model_for_data = False
            for model_id, model_meta in self.models.items():
                if model_meta.get('data_pos') == record_pos:
                    self.details.insert(tk.END, f"Associated with Model Header:\n")
                    self.details.insert(tk.END, f"  Vertices: {model_meta['vertex_count']}\n")
                    self.details.insert(tk.END, f"  Faces: {model_meta['face_count']}\n")
                    found_model_for_data = True
                    break
            if not found_model_for_data:
                self.details.insert(tk.END, "Model data found, but no associated header.\n")

        elif record_type in [RECORD_TYPE_ANIMATION_DATA, RECORD_TYPE_ANIMATION_DATA2]:
            frame_count, duration = self.parse_animation_data(record_data)
            self.details.insert(tk.END, f"Animation Info: {frame_count} frames, {duration:.2f} seconds\n")

        elif record_type in [RECORD_TYPE_ENTITY_PLACEMENT, RECORD_TYPE_ENTITY_PLACEMENT2, 
                           RECORD_TYPE_ENTITY_PLACEMENT_BCC, RECORD_TYPE_ENTITY_PLACEMENT_LEVEL]:
            x, y, z = self.parse_entity_data(record_data)
            self.details.insert(tk.END, f"Entity Position: X={x:.2f}, Y={y:.2f}, Z={z:.2f}\n")

        # Display hex dump of the first few bytes
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
