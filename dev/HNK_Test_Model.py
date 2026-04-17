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


# Detect vertex size using FFFFFFFF separators
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
        return 48

    return max(set(sizes), key=sizes.count)


# Simple UV offset guess
def detect_uv_offset(vertex_size):

    possible = [12, 16, 20, 24, 28, 32]

    for off in possible:
        if off + 8 <= vertex_size:
            return off

    return 12


def extract_vertices(data, vertex_size, uv_offset):

    vertices = []
    uvs = []

    num_vertices = len(data) // vertex_size

    for i in range(num_vertices):

        offset = i * vertex_size

        try:
            x, y, z = struct.unpack("<3f", data[offset:offset+12])

            if math.isnan(x) or math.isinf(x): x = 0.0
            if math.isnan(y) or math.isinf(y): y = 0.0
            if math.isnan(z) or math.isinf(z): z = 0.0

        except:
            x, y, z = 0.0, 0.0, 0.0

        u, v = 0.0, 0.0

        if offset + uv_offset + 8 <= len(data):
            try:
                u, v = struct.unpack("<2f", data[offset+uv_offset:offset+uv_offset+8])

                if math.isnan(u) or math.isinf(u): u = 0.0
                if math.isnan(v) or math.isinf(v): v = 0.0

            except:
                pass

        vertices.append((x, y, z))
        uvs.append((u, 1.0 - v))

    return vertices, uvs


def extract_indices(data):

    indices = []

    for i in range(0, len(data) - 1, 2):

        idx = struct.unpack("<H", data[i:i+2])[0]

        if idx != 0xFFFF:
            indices.append(idx)

    return indices


def export_model(hnk_path):
    records = read_hunkfile(hnk_path)

    v_raw_records = [data for t, data in records if t == 0x40054]
    i_raw_records = [data for t, data in records if t == 0x20055]

    all_v = []
    all_uv = []
    all_f = []
    global_obj_v_offset = 0

    # Iterujemy po parach Rekord Wierzchołków <-> Rekord Indeksów
    for block_idx in range(min(len(v_raw_records), len(i_raw_records))):
        v_data = v_raw_records[block_idx]
        i_data = i_raw_records[block_idx]

        # 1. Wyciągamy WSZYSTKIE wierzchołki z tego dużego bloku
        v_size = detect_vertex_size(v_data)
        uv_off = detect_uv_offset(v_size)
        full_v_list, full_uv_list = extract_vertices(v_data, v_size, uv_off)

        # 2. Dekodujemy indeksy i szukamy restartów (batchy)
        indices = []
        for i in range(0, len(i_data) - 1, 2):
            indices.append(struct.unpack("<H", i_data[i:i+2])[0])

        batches = []
        current_batch = []
        for i in range(len(indices)):
            # Wykrywanie restartu indeksu do 0 (nowa pod-część w tym samym bloku)
            if i > 2 and indices[i] == 0 and indices[i+1] == 1:
                if current_batch:
                    batches.append(current_batch)
                    current_batch = []
            current_batch.append(indices[i])
        if current_batch:
            batches.append(current_batch)

        print(f"Blok {block_idx+1}: Znaleziono {len(batches)} pod-części wewnątrz {len(full_v_list)} wierzchołków.")

        # 3. Przypisujemy każdą pod-część indeksów do odpowiedniego fragmentu wierzchołków
        local_block_offset = 0
        for b_idx, batch in enumerate(batches):
            max_idx_in_batch = max(batch)
            
            # Budujemy trójkąty
            for j in range(0, len(batch) - 2, 3):
                a, b, c = batch[j], batch[j+1], batch[j+2]
                
                # Klucz: Indeks globalny w OBJ to:
                # indeks_w_batchu + offset_w_obecnym_bloku + całkowity_offset_obj
                all_f.append((
                    a + 1 + local_block_offset + global_obj_v_offset,
                    b + 1 + local_block_offset + global_obj_v_offset,
                    c + 1 + local_block_offset + global_obj_v_offset
                ))
            
            # Po każdej pod-części zwiększamy lokalny offset o liczbę zużytych wierzchołków
            # Zazwyczaj jest to max_index + 1
            local_block_offset += (max_idx_in_batch + 1)

        # Na koniec dodajemy wszystkie wierzchołki z tego bloku do listy globalnej
        all_v.extend(full_v_list)
        all_uv.extend(full_uv_list)
        global_obj_v_offset += len(full_v_list)

    save_obj_final(hnk_path, all_v, all_uv, all_f)

def save_obj_final(path, verts, uvs, faces):
    out_path = path.replace(".hnk", "_complete.obj")
    with open(out_path, "w") as f:
        f.write("# HNK Reconstructed Model\n")
        # Zapisz wszystkie wierzchołki
        for v in verts:
            f.write(f"v {v[0]:.6f} {v[1]:.6f} {v[2]:.6f}\n")
        # Zapisz wszystkie UV
        for uv in uvs:
            f.write(f"vt {uv[0]:.6f} {uv[1]:.6f}\n")
        # Zapisz wszystkie trójkąty
        for face in faces:
            # v1/uv1 v2/uv2 v3/uv3
            f.write(f"f {face[0]}/{face[0]} {face[1]}/{face[1]} {face[2]}/{face[2]}\n")
    print(f"Model zapisany poprawnie: {out_path}")

def select_file():

    path = filedialog.askopenfilename(
        title="Select HNK file",
        filetypes=[("HNK files", "*.hnk"), ("All files", "*.*")]
    )

    if not path:
        return

    try:

        export_model(path)

        messagebox.showinfo(
            "Finished",
            "Export completed.\n\nNote:\nThis tool is still in development.\nCurrently only the second mesh exports correctly."
        )

    except Exception as e:

        messagebox.showerror("Error", str(e))


def main():

    root = tk.Tk()
    root.title("HNK Model Extractor")
    root.geometry("420x200")

    label = tk.Label(
        root,
        text="HNK Model Extractor\n\nThis tool is incomplete and still in development.\nOnly the second part of the model exports correctly.",
        justify="center"
    )

    label.pack(pady=25)

    btn = tk.Button(
        root,
        text="Select .HNK File",
        width=20,
        command=select_file
    )

    btn.pack(pady=10)

    root.mainloop()


if __name__ == "__main__":
    main()
