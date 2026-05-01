import os
import struct
import io
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from PIL import Image, ImageTk

class HnkSpriteExtractorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("HNK RenderSprite & Texture Extractor (Smart Match)")
        self.root.geometry("1100x750")

        self.file_data = b""
        self.textures_dict = {}  # { "Font_UI0": PIL.Image }
        self.sprites_dict = {}   # { "Font_UI": [ {id, hash, ...}, ... ] }

        # --- TOP PANEL ---
        top_frame = tk.Frame(root)
        top_frame.pack(fill="x", padx=10, pady=5)

        self.btn_load = tk.Button(top_frame, text="Load .hnk File", command=self.load_file, font=("Arial", 10, "bold"), bg="#FF9800", fg="white")
        self.btn_load.pack(side="left", padx=5)

        self.lbl_file = tk.Label(top_frame, text="No file loaded", fg="gray")
        self.lbl_file.pack(side="left", padx=10)

        self.btn_export_all = tk.Button(top_frame, text="Save All Sprites (PNG)", command=self.export_all_sprites, state=tk.DISABLED)
        self.btn_export_all.pack(side="right", padx=5)

        # --- MAIN PANEL ---
        main_frame = tk.PanedWindow(root, orient=tk.HORIZONTAL)
        main_frame.pack(fill="both", expand=True, padx=10, pady=(0, 5))

        # LEFT SIDE: Render Sprite List
        left_frame = tk.Frame(main_frame)
        tk.Label(left_frame, text="Found Objects:", font=("Arial", 10, "bold")).pack(anchor="w")
        
        self.listbox = tk.Listbox(left_frame, exportselection=False)
        self.listbox.pack(fill="both", expand=True)
        self.listbox.bind("<<ListboxSelect>>", self.on_item_select)
        main_frame.add(left_frame, minsize=200)

        # MIDDLE: Table
        mid_frame = tk.Frame(main_frame)
        tk.Label(mid_frame, text="Sprite Details:", font=("Arial", 10, "bold")).pack(anchor="w")

        cols = ("id", "hash", "u1", "v1", "u2", "v2")
        self.tree = ttk.Treeview(mid_frame, columns=cols, show="headings", selectmode="browse")
        for c in cols:
            self.tree.heading(c, text=c.upper())
            self.tree.column(c, width=60, anchor="center")
        self.tree.column("hash", width=80)
        
        self.tree.bind("<<TreeviewSelect>>", self.on_sprite_select)
        
        scroll = ttk.Scrollbar(mid_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscroll=scroll.set)
        self.tree.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        main_frame.add(mid_frame, minsize=380)

        # RIGHT SIDE: Image Preview
        right_frame = tk.Frame(main_frame)
        tk.Label(right_frame, text="Texture/Sprite Preview:", font=("Arial", 10, "bold")).pack(anchor="w")
        
        self.canvas = tk.Canvas(right_frame, bg="#2b2b2b", width=256, height=256)
        self.canvas.pack(pady=10)
        
        self.btn_export_single = tk.Button(right_frame, text="Save Selected Sprite", command=self.export_single_sprite, state=tk.DISABLED)
        self.btn_export_single.pack()
        
        main_frame.add(right_frame, minsize=280)
        self.current_preview_image = None

        # --- (DEBUG LOG)
        bottom_frame = tk.Frame(root)
        bottom_frame.pack(fill="x", padx=10, pady=5)
        tk.Label(bottom_frame, text="Operation Log (Debug):", font=("Arial", 9, "bold")).pack(anchor="w")
        
        self.log_text = tk.Text(bottom_frame, height=8, bg="#f4f4f4", font=("Consolas", 9))
        self.log_text.pack(fill="x")
        self.log_text.config(state=tk.DISABLED)

    def log(self, message):
        self.log_text.config(state=tk.NORMAL)
        self.log_text.insert(tk.END, message + "\n")
        self.log_text.see(tk.END)
        self.log_text.config(state=tk.DISABLED)
        self.root.update()

    def get_texture_for_sprite(self, sprite_name):
        if sprite_name in self.textures_dict:
            return self.textures_dict[sprite_name]
        elif f"{sprite_name}0" in self.textures_dict:
            return self.textures_dict[f"{sprite_name}0"]
        return None

    # ==========================================
    #      DECODE (DDS)
    # ==========================================
    def create_dds_header(self, width, height, texture_format):
        header = bytearray(128)
        header[0:4] = b"DDS "
        header[4:8] = (124).to_bytes(4, "little")
        flags = 0x1 | 0x2 | 0x4 | 0x1000
        if texture_format in ["DXT1", "DXT5"]:
            flags |= 0x80000
            block_size = 8 if texture_format == "DXT1" else 16
            linear_size = max(1, (width + 3) // 4) * max(1, (height + 3) // 4) * block_size
        else:
            flags |= 0x8
            linear_size = width * 4
            
        header[8:12] = flags.to_bytes(4, "little")
        header[12:16] = height.to_bytes(4, "little")
        header[16:20] = width.to_bytes(4, "little")
        header[20:24] = linear_size.to_bytes(4, "little")
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
            
        header[108:112] = (0x1000).to_bytes(4, "little")
        return header

    def parse_blocks(self, type_string, magic_bytes):
        results = []
        search_kw = type_string.encode('ascii') + b'\x00'
        start = 0
        while True:
            idx = self.file_data.find(search_kw, start)
            if idx == -1: break
            
            name_start = idx + len(search_kw)
            name_end = self.file_data.find(b'\x00', name_start)
            raw_name = self.file_data[name_start:name_end]
            name = raw_name.decode('ascii', errors='ignore').strip('\x00').strip()
            
            magic_idx = self.file_data.find(magic_bytes, name_end)
            if magic_idx != -1 and (magic_idx - name_end) <= 32:
                size_bytes = self.file_data[magic_idx-4 : magic_idx]
                chunk_size = int.from_bytes(size_bytes, 'little')
                chunk_data_start = magic_idx + 4
                chunk_data = self.file_data[chunk_data_start : chunk_data_start + chunk_size]
                
                results.append({'name': name, 'size': chunk_size, 'data': chunk_data, 'end_offset': chunk_data_start + chunk_size})
                self.log(f"[OK] {type_string}: '{name}' | Size: {chunk_size} bytes.")
            start = name_end
        return results

    def load_file(self):
        filepath = filedialog.askopenfilename(title="Select .hnk file")
        if not filepath: return

        self.lbl_file.config(text=os.path.basename(filepath), fg="black")
        with open(filepath, 'rb') as f: self.file_data = f.read()

        self.textures_dict.clear()
        self.sprites_dict.clear()
        self.listbox.delete(0, tk.END)
        
        self.log_text.config(state=tk.NORMAL)
        self.log_text.delete(1.0, tk.END)
        self.log_text.config(state=tk.DISABLED)

        self.log("=== STARTING FILE SCAN ===")
        self.parse_textures()
        self.parse_sprites()
        
        for name in self.sprites_dict.keys():
            if self.get_texture_for_sprite(name):
                self.listbox.insert(tk.END, f"{name} [✔]")
            else:
                self.listbox.insert(tk.END, f"{name} [❌ No Texture]")

    def parse_textures(self):
        self.log("\n--- SEARCHING FOR TEXTURES (TSETexture) ---")
        blocks = self.parse_blocks("TSETexture", b'\x50\x11\x04\x00')
        for block in blocks:
            name = block['name']
            header_data = block['data']
            try:
                width = struct.unpack('<H', header_data[0x0C:0x0E])[0]
                height = struct.unpack('<H', header_data[0x0E:0x10])[0]
                fmt_marker = header_data[0x00:0x02]
                
                tex_format = "DXT1"
                if fmt_marker == b'\xD3\x3A': tex_format = "DXT5"
                elif fmt_marker == b'\x6F\x74': tex_format = "R8G8B8A8"

                next_offset = block['end_offset']
                if next_offset + 8 <= len(self.file_data):
                    data_size = int.from_bytes(self.file_data[next_offset : next_offset+4], 'little')
                    data_magic = self.file_data[next_offset+4 : next_offset+8]
                    
                    if data_magic == b'\x51\x01\x04\x00':
                        tex_data = self.file_data[next_offset+8 : next_offset+8+data_size]
                        dds_header = self.create_dds_header(width, height, tex_format)
                        with io.BytesIO(dds_header + tex_data) as dds_file:
                            img = Image.open(dds_file).convert("RGBA")
                            self.textures_dict[name] = img
                            self.log(f"  [SUCCESS] Loaded texture '{name}'")
            except Exception as e:
                self.log(f"  [ERROR] {name}: {e}")

    def parse_sprites(self):
        self.log("\n--- SEARCHING FOR SPRITES (RenderSprite) ---")
        blocks = self.parse_blocks("RenderSprite", b'\x07\x10\x04\x00')
        for block in blocks:
            name = block['name']
            chunk_data = block['data']
            try:
                first_pointer = int.from_bytes(chunk_data[16:20], 'little')
                num_sprites = (first_pointer - 16) // 4
                
                parsed = []
                for i in range(num_sprites):
                    ptr = int.from_bytes(chunk_data[16 + (i*4) : 16 + (i*4) + 4], 'little')
                    sp_data = chunk_data[ptr : ptr + 64]
                    if len(sp_data) == 64:
                        hash_val = sp_data[0:4].hex().upper()
                        u1, v1, u2, v2 = struct.unpack('<ffff', sp_data[16:32])
                        parsed.append({'id': i, 'hash': hash_val, 'u1': u1, 'v1': v1, 'u2': u2, 'v2': v2})
                self.sprites_dict[name] = parsed
            except Exception as e:
                self.log(f"  [ERROR] {name}: {e}")

    def on_item_select(self, event):
        for row in self.tree.get_children(): self.tree.delete(row)
        selection = self.listbox.curselection()
        if not selection: return

        selected_display = self.listbox.get(selection[0])
        name = selected_display.split(" [")[0]
        
        for sp in self.sprites_dict.get(name, []):
            self.tree.insert("", "end", values=(sp['id'], sp['hash'], round(sp['u1'],3), round(sp['v1'],3), round(sp['u2'],3), round(sp['v2'],3)))

        texture = self.get_texture_for_sprite(name)
        if texture:
            self.show_preview(texture)
            self.btn_export_all.config(state=tk.NORMAL)
        else:
            self.canvas.delete("all")
            self.canvas.create_text(128, 128, text="No image", fill="white")
            self.btn_export_all.config(state=tk.DISABLED)
            self.btn_export_single.config(state=tk.DISABLED)

    def on_sprite_select(self, event):
        selection = self.tree.selection()
        if not selection: return
        
        list_selection = self.listbox.curselection()
        if not list_selection: return
        name = self.listbox.get(list_selection[0]).split(" [")[0]

        img = self.get_texture_for_sprite(name)
        if not img: return

        item = self.tree.item(selection[0])['values']
        u1, v1, u2, v2 = float(item[2]), float(item[3]), float(item[4]), float(item[5])
        
        w, h = img.width, img.height
        x1, y1 = int(u1 * w), int(v1 * h)
        x2, y2 = int(u2 * w), int(v2 * h)
        
        left, right = min(x1, x2), max(x1, x2)
        top, bottom = min(y1, y2), max(y1, y2)

        if right > left and bottom > top:
            cropped = img.crop((left, top, right, bottom))
            self.show_preview(cropped)
            self.current_preview_image = cropped
            self.btn_export_single.config(state=tk.NORMAL)

    def show_preview(self, img):
        self.canvas.delete("all")
        img_w, img_h = img.width, img.height
        max_size = 250
        ratio = min(max_size/img_w, max_size/img_h)
        new_size = (max(1, int(img_w * ratio)), max(1, int(img_h * ratio)))
        
        resized = img.resize(new_size, Image.Resampling.LANCZOS)
        self.tk_image = ImageTk.PhotoImage(resized)
        self.canvas.create_image(128, 128, anchor="center", image=self.tk_image)

    def export_single_sprite(self):
        if not self.current_preview_image: return
        path = filedialog.asksaveasfilename(defaultextension=".png", filetypes=[("PNG", "*.png")])
        if path:
            self.current_preview_image.save(path, "PNG")
            messagebox.showinfo("Success", "Sprite exported successfully!")

    def export_all_sprites(self):
        selection = self.listbox.curselection()
        if not selection: return
        name = self.listbox.get(selection[0]).split(" [")[0]
        
        folder = filedialog.askdirectory(title="Select folder to save sprites")
        if not folder: return
        
        img = self.get_texture_for_sprite(name)
        if not img: return
        w, h = img.width, img.height
        
        count = 0
        for sp in self.sprites_dict[name]:
            x1, y1 = int(sp['u1'] * w), int(sp['v1'] * h)
            x2, y2 = int(sp['u2'] * w), int(sp['v2'] * h)
            left, right = min(x1, x2), max(x1, x2)
            top, bottom = min(y1, y2), max(y1, y2)
            
            if right > left and bottom > top:
                cropped = img.crop((left, top, right, bottom))
                save_path = os.path.join(folder, f"{name}_{sp['hash']}.png")
                cropped.save(save_path, "PNG")
                count += 1
                
        messagebox.showinfo("Done!", f"Saved {count} PNG images.")

if __name__ == "__main__":
    root = tk.Tk()
    app = HnkSpriteExtractorApp(root)
    root.mainloop()
