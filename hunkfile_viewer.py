# hunkfile_viewer.py
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from tkinter.scrolledtext import ScrolledText
import struct
import os
from PIL import Image, ImageTk
from record_types import *
from PC.pc_texture_decoder import PCTextureDecoder
from Wii.wii_texture_decoder import WiiTextureDecoder

class HunkfileViewer:
    def __init__(self, root):
        self.root = root
        self.root.title("Hunkfile Viewer")
        self.records = []
        self.current_file = None
        self.texture_image = None
        self.textures = {}
        self.texture_decoder = None
        self.platform_label = None
        self.create_widgets()
        self.setup_context_menu()

    def setup_context_menu(self):
        self.context_menu = tk.Menu(self.root, tearoff=0)
        self.context_menu.add_command(label="Extract to .dat file", command=self.extract_selected_record)
        self.tree.bind("<Button-3>", self.show_context_menu)

    def show_context_menu(self, event):
        item = self.tree.identify_row(event.y)
        if item:
            self.tree.selection_set(item)
            self.context_menu.post(event.x_root, event.y_root)

    def extract_selected_record(self):
        selection = self.tree.selection()
        if not selection:
            return
        try:
            record_index = int(selection[0])
            _record_size, record_type, record_data, record_pos = self.records[record_index]
        except (ValueError, IndexError):
            messagebox.showerror("Error", "Could not retrieve record data for extraction.")
            return
        default_filename = f"record_0x{record_type:08X}_at_{record_pos}.dat"
        if record_type == FILENAME_HEADER:
            folder, filename = self.parse_filename_header(record_data)
            if filename and filename != "ErrorParsing":
                default_filename = filename + ".dat"
        output_path = filedialog.asksaveasfilename(
            title="Save Record Data",
            initialfile=default_filename,
            defaultextension=".dat",
            filetypes=(("DAT files", "*.dat"), ("All files", "*.*"))
        )
        if not output_path:
            return
        try:
            with open(output_path, 'wb') as f:
                f.write(record_data)
            messagebox.showinfo("Success", f"Record data successfully extracted to:\n{output_path}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save record data:\n{str(e)}")

    def create_widgets(self):
        self.platform_label = tk.Label(
            self.root,
            text="Platform: Unknown",
            font=("Arial", 12, "bold"),
            bg="lightgrey",
            anchor="w",
            padx=10,
            pady=5
        )
        self.platform_label.pack(fill=tk.X, padx=5, pady=2)
        main_panel = tk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        main_panel.pack(fill=tk.BOTH, expand=True)
        left_panel = tk.Frame(main_panel, width=300)
        main_panel.add(left_panel)
        right_panel = tk.PanedWindow(main_panel, orient=tk.VERTICAL)
        main_panel.add(right_panel)
        button_frame = tk.Frame(left_panel)
        button_frame.pack(fill=tk.X, padx=5, pady=5)
        open_button = tk.Button(button_frame, text="Open HNK File", command=self.open_file)
        open_button.pack(side=tk.LEFT, expand=True)
        self.tree = ttk.Treeview(left_panel, columns=("Type", "Size", "Details"), show="headings")
        self.tree.heading("Type", text="Record Type")
        self.tree.heading("Size", text="Record Size")
        self.tree.heading("Details", text="Details")
        self.tree.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        details_frame = tk.Frame(right_panel)
        right_panel.add(details_frame)
        self.details = ScrolledText(details_frame, height=10)
        self.details.pack(fill=tk.BOTH, expand=True)
        self.texture_frame = tk.LabelFrame(right_panel, text="Texture Preview", height=400)
        right_panel.add(self.texture_frame)
        self.canvas = tk.Canvas(self.texture_frame, bg='white')
        self.canvas.pack(fill=tk.BOTH, expand=True)
        self.scrollbar_y = tk.Scrollbar(self.texture_frame, orient=tk.VERTICAL, command=self.canvas.yview)
        self.scrollbar_y.pack(side=tk.RIGHT, fill=tk.Y)
        self.scrollbar_x = tk.Scrollbar(self.texture_frame, orient=tk.HORIZONTAL, command=self.canvas.xview)
        self.scrollbar_x.pack(side=tk.BOTTOM, fill=tk.X)
        self.canvas.configure(yscrollcommand=self.scrollbar_y.set, xscrollcommand=self.scrollbar_x.set)
        self.canvas.bind('<Configure>', lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.tree.bind("<<TreeviewSelect>>", self.show_details)

    def detect_platform(self, records):
        for record_size, record_type, record_data, _ in records:
            if record_type == HUNKFILE_HEADER and len(record_data) >= 5:
                if record_data[:5] in (b'\x01\x00\x01\x00\x01', b'\xE5\x0A\x01\x00\x01'):
                    return "PC"
                else:
                    return "Wii"
        return "Wii"  # Default to Wii if no Hunk header is found

    def open_file(self):
        file_path = filedialog.askopenfilename(
            title="Open HNK File",
            filetypes=(("HNK files", "*.hnk"), ("All files", "*.*"))
        )
        if not file_path:
            return
        self.current_file = file_path
        self.root.title(f"Hunkfile Viewer - {os.path.basename(file_path)}")
        try:
            parsed_records = self.read_hunkfile(file_path)
            platform = self.detect_platform(parsed_records)
            self.platform_label.config(text=f"Platform: {platform}")
            self.texture_decoder = PCTextureDecoder() if platform == "PC" else WiiTextureDecoder()
            self.populate_tree(parsed_records)
        except Exception as e:
            self.platform_label.config(text="Platform: Error")
            messagebox.showerror("Error", f"Failed to read or parse HNK file:\n{str(e)}")

    def read_hunkfile(self, filename):
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
        try:
            values = struct.unpack('<hhhhh', data[:10])
            folder_length = values[3]
            filename_length = values[4]
            folder_offset = 10
            filename_offset = 10 + folder_length
            folder = data[folder_offset : folder_offset + folder_length].decode('utf-8', errors='ignore').rstrip('\x00')
            filename = data[filename_offset : filename_offset + filename_length].decode('utf-8', errors='ignore').rstrip('\x00')
            return folder, filename
        except (struct.error, IndexError):
            return "ErrorParsing", "ErrorParsing"

    def show_texture(self, texture_data, width, height, texture_format):
        self.canvas.delete("all")
        if width == 0 or height == 0:
            self.canvas.create_text(50, 50, text="Invalid texture dimensions (0x0).", fill="orange")
            return False
        format_text = f"Format: {texture_format} | Dimensions: {width}x{height}"
        self.canvas.create_text(10, 10, text=format_text, anchor=tk.NW, fill="black")
        try:
            img = self.texture_decoder.decode_texture(texture_data, width, height, texture_format)
            if img is None:
                raise ValueError("Failed to decode texture")
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
        self.tree.delete(*self.tree.get_children())
        self.records = parsed_records
        self.canvas.delete("all")
        self.details.delete(1.0, tk.END)
        self.textures.clear()
        current_texture_id_awaiting_data = None

        record_type_names = {
            HUNKFILE_HEADER: "Hunkfile Header",
            FILENAME_HEADER: "Filename Header",
            EMPTY: "Empty",
            ABSTRACT_HASH_IDENTIFIER: "Abstract Hash Identifier",
            TSE_STRING_TABLE_MAIN: "TSE String Table Main",
            CLANK_BODY_TEMPLATE_MAIN: "Clank Body Template Main",
            CLANK_BODY_TEMPLATE_SECONDARY: "Clank Body Template Secondary",
            CLANK_BODY_TEMPLATE_NAME: "Clank Body Template Name",
            CLANK_BODY_TEMPLATE_DATA: "Clank Body Template Data",
            CLANK_BODY_TEMPLATE_DATA_2: "Clank Body Template Data 2",
            LITE_SCRIPT_MAIN: "Lite Script Main",
            LITE_SCRIPT_DATA: "Lite Script Data",
            LITE_SCRIPT_DATA_2: "Lite Script Data 2",
            SQUEAK_SAMPLE_DATA: "Squeak Sample Data",
            TSE_TEXTURE_HEADER: "TSE Texture Header",
            TSE_TEXTURE_DATA: "TSE Texture Data",
            TSE_TEXTURE_DATA_2: "TSE Texture Data 2",
            RENDER_MODEL_TEMPLATE_HEADER: "Render Model Template Header",
            RENDER_MODEL_TEMPLATE_DATA: "Render Model Template Data",
            RENDER_MODEL_TEMPLATE_DATA_TABLE: "Render Model Template Data Table",
            ANIMATION_DATA: "Animation Data",
            ANIMATION_DATA_2: "Animation Data 2",
            RENDER_SPRITE_DATA: "Render Sprite Data",
            EFFECTS_PARAMS_DATA: "Effects Params Data",
            TSE_FONT_DESCRIPTOR_DATA: "TSE Font Descriptor Data",
            TSE_DATA_TABLE_DATA_1: "TSE Data Table Data 1",
            TSE_DATA_TABLE_DATA_2: "TSE Data Table Data 2",
            STATE_FLOW_TEMPLATE_DATA: "State Flow Template Data",
            STATE_FLOW_TEMPLATE_DATA_2: "State Flow Template Data 2",
            SQUEAK_STREAM_DATA: "Squeak Stream Data",
            SQUEAK_STREAM_DATA_2: "Squeak Stream Data 2",
            ENTITY_PLACEMENT_DATA: "Entity Placement Data",
            ENTITY_PLACEMENT_DATA_2: "Entity Placement Data 2",
            ENTITY_PLACEMENT_BCC_DATA: "Entity Placement BCC Data",
            ENTITY_PLACEMENT_LEVEL_DATA: "Entity Placement Level Data",
            ENTITY_TEMPLATE_DATA: "Entity Template Data",
            TSE_TEXTURE_DATA_WII: "TSE Texture Data (Wii)"
        }

        for i, (record_size, record_type, record_data, record_pos) in enumerate(self.records):
            details_summary = record_type_names.get(record_type, f"Unknown (0x{record_type:08X})")
            if record_type == FILENAME_HEADER:
                folder, filename = self.parse_filename_header(record_data)
                details_summary = f"File: {filename}"
                if folder:
                    details_summary += f" (in {folder})"
            elif record_type == TSE_TEXTURE_HEADER:
                width, height, texture_format = self.texture_decoder.parse_texture_header(record_data)
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
            elif record_type in (TSE_TEXTURE_DATA, TSE_TEXTURE_DATA_WII, TSE_TEXTURE_DATA_2):
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
        if record_type == FILENAME_HEADER:
            folder, filename = self.parse_filename_header(record_data)
            self.details.insert(tk.END, f"Parsed Folder: {folder}\n")
            self.details.insert(tk.END, f"Parsed Filename: {filename}\n")
        elif record_type == TSE_TEXTURE_HEADER:
            width, height, texture_format = self.texture_decoder.parse_texture_header(record_data)
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
        elif record_type in (TSE_TEXTURE_DATA, TSE_TEXTURE_DATA_WII, TSE_TEXTURE_DATA_2):
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
