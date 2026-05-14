import struct
import os
import math
import tkinter as tk
from tkinter import filedialog, messagebox


def read_hunkfile(filename):
    records = []
    with open(filename, 'rb') as f:
        while True:
            size_bytes = f.read(4)
            if not size_bytes:
                break

            type_bytes = f.read(4)
            if not type_bytes:
                break

            record_size = struct.unpack("<I", size_bytes)[0]
            record_type = struct.unpack("<I", type_bytes)[0]
            data = f.read(record_size)

            if len(data) < record_size:
                break

            records.append((record_type, data))

    return records


def detect_vertex_size(data):
    sizes = []
    last = 0
    for i in range(0, len(data) - 3, 4):
        if data[i:i+4] == b'\xFF\xFF\xFF\xFF':
            size = (i + 4) - last
            if 16 <= size <= 128:
                sizes.append(size)
            last = i + 4
        if len(sizes) >= 10:
            break
    if not sizes:
        return 64
    return max(set(sizes), key=sizes.count)


def extract_vertices(data, vertex_size, uv_offset):
    vertices = []
    uvs = []

    num_vertices = len(data) // vertex_size

    for i in range(num_vertices):
        offset = i * vertex_size
        vertex_data = data[offset : offset + vertex_size]

        try:
            x, y, z = struct.unpack("<3f", vertex_data[0:12])
            if math.isnan(x) or math.isinf(x): x = 0.0
            if math.isnan(y) or math.isinf(y): y = 0.0
            if math.isnan(z) or math.isinf(z): z = 0.0
        except:
            x, y, z = 0.0, 0.0, 0.0

        u, v = 0.0, 0.0

        marker_pos = vertex_data.find(b'\xFF\xFF\xFF\xFF')
        
        if marker_pos != -1 and marker_pos + 4 + 8 <= vertex_size:
            uv_start = marker_pos + 4
        else:
            uv_start = uv_offset

        if uv_start + 8 <= vertex_size:
            try:
                u, v = struct.unpack("<2f", vertex_data[uv_start : uv_start + 8])
                if math.isnan(u) or math.isinf(u): u = 0.0
                if math.isnan(v) or math.isinf(v): v = 0.0
            except:
                pass

        vertices.append((x, y, z))
        uvs.append((u, 1.0 - v)) 

    return vertices, uvs

def extract_model_name(data):
    marker = b"RenderModelTemplate\x00"
    idx = data.find(marker)
    if idx != -1:
        start_idx = idx + len(marker)
        end_idx = data.find(b"\x00", start_idx)
        if end_idx != -1:
            # Odczytujemy nazwę i usuwamy niedozwolone znaki dla nazw plików
            raw_name = data[start_idx:end_idx].decode('utf-8', errors='ignore')
            safe_name = "".join(c for c in raw_name if c.isalnum() or c in " _-")
            return safe_name
    return None


def export_model(hnk_path, split_all_subparts):
    records = read_hunkfile(hnk_path)

    models = []
    current_v_records = []
    current_i_records = []
    current_name = None

    for rec_type, data in records:
        if rec_type == 0x40071:
            
            if current_v_records or current_i_records:
                models.append((current_v_records, current_i_records, current_name))
                current_v_records = []
                current_i_records = []
                current_name = None
            
            # Czasami nazwa może być w samym bloku 0x40071
            name = extract_model_name(data)
            if name: current_name = name

        elif rec_type == 0x40054:
            current_v_records.append(data)
        elif rec_type == 0x20055:
            current_i_records.append(data)
        else:
            if not current_name:
                name = extract_model_name(data)
                if name: current_name = name

    # Dodajemy ostatni model z pętli
    if current_v_records or current_i_records:
        models.append((current_v_records, current_i_records, current_name))

    if not models:
        raise Exception("Nie znaleziono danych modeli w pliku!")

    base_path, _ = os.path.splitext(hnk_path)
    exported_count = 0
    
    used_names = {}

    for model_idx, (v_raw_records, i_raw_records, model_name) in enumerate(models):
        
        # Generowanie nazwy pliku
        if not model_name:
            model_name = f"Model_{model_idx}"
            
        if model_name in used_names:
            used_names[model_name] += 1
            final_name = f"{model_name}_{used_names[model_name]}"
        else:
            used_names[model_name] = 1
            final_name = model_name

        out_path = f"{base_path}_{final_name}.obj"
        
        with open(out_path, "w") as f_out:
            f_out.write(f"# HNK Reconstructed Model: {final_name}\n")
            f_out.write(f"# Split All Subparts Mode: {split_all_subparts}\n\n")

            global_vertex_counter = 0 

            for block_idx in range(min(len(v_raw_records), len(i_raw_records))):
                v_data = v_raw_records[block_idx]
                i_data = i_raw_records[block_idx]

                v_size = detect_vertex_size(v_data)
                uv_off = 44 if v_size == 64 else 12 
                
                full_v_list, full_uv_list = extract_vertices(v_data, v_size, uv_off)

                for v in full_v_list:
                    f_out.write(f"v {v[0]:.6f} {v[1]:.6f} {v[2]:.6f}\n")
                for uv in full_uv_list:
                    f_out.write(f"vt {uv[0]:.6f} {uv[1]:.6f}\n")

                indices = []
                for i in range(0, len(i_data) - 1, 2):
                    indices.append(struct.unpack("<H", i_data[i:i+2])[0])

                batches = []
                current_batch = []
                for i in range(len(indices)):
                    if i > 2 and indices[i] == 0 and indices[i+1] == 1:
                        if current_batch:
                            batches.append(current_batch)
                            current_batch = []
                    current_batch.append(indices[i])
                if current_batch:
                    batches.append(current_batch)

                if not split_all_subparts:
                    part_name = f"Block_{block_idx}"
                    f_out.write(f"\no {part_name}\n")
                    f_out.write(f"g {part_name}\n")

                local_block_offset = 0
                
                for b_idx, batch in enumerate(batches):
                    if not batch:
                        continue
                    
                    if split_all_subparts:
                        part_name = f"Block_{block_idx}_Part_{b_idx}"
                        f_out.write(f"\no {part_name}\n")
                        f_out.write(f"g {part_name}\n")
                    
                    max_idx_in_batch = max(batch)
                    
                    for j in range(0, len(batch) - 2, 3):
                        a, b, c = batch[j], batch[j+1], batch[j+2]
                        
                        idx_a = a + 1 + local_block_offset + global_vertex_counter
                        idx_b = b + 1 + local_block_offset + global_vertex_counter
                        idx_c = c + 1 + local_block_offset + global_vertex_counter
                        
                        f_out.write(f"f {idx_a}/{idx_a} {idx_b}/{idx_b} {idx_c}/{idx_c}\n")
                    
                    local_block_offset += (max_idx_in_batch + 1)

                global_vertex_counter += len(full_v_list)

        print(f"Zapisano poprawnie plik: {out_path}")
        exported_count += 1

    return exported_count

split_var = None 

def select_file():
    global split_var
    path = filedialog.askopenfilename(
        title="Wybierz plik HNK",
        filetypes=[("HNK files", "*.hnk"), ("All files", "*.*")]
    )

    if not path:
        return

    try:
        do_split = split_var.get()
        exported = export_model(path, do_split)

        messagebox.showinfo(
            "Done",
            f"Exported {exported} to files .obj."
        )
    except Exception as e:
        messagebox.showerror("Błąd", str(e))


def main():
    global split_var
    
    root = tk.Tk()
    root.title("HNK Model Extractor")
    root.geometry("450x250")

    label = tk.Label(
        root,
        text="HNK Model Extractor",
        justify="center"
    )
    label.pack(pady=15)

    split_var = tk.BooleanVar(value=False)
    chk_btn = tk.Checkbutton(
        root, 
        text="Export all submesh", 
        variable=split_var,
        justify="left"
    )
    chk_btn.pack(pady=10)

    btn = tk.Button(
        root,
        text="Select .hnk File",
        width=20,
        height=2,
        command=select_file
    )
    btn.pack(pady=10)

    root.mainloop()


if __name__ == "__main__":
    main()
