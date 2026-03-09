#### The code is in development and helps me analyze models, it has many bugs and models can come out completely broken

import struct
import os
import math
import tkinter as tk
from tkinter import filedialog, messagebox


def read_hunkfile(filename):
    records = []
    with open(filename, 'rb') as fp:
        while True:
            size_bytes = fp.read(4)
            if not size_bytes:
                break
            type_bytes = fp.read(4)
            if not type_bytes:
                break

            record_size = struct.unpack('<I', size_bytes)[0]
            record_type = struct.unpack('<I', type_bytes)[0]
            data = fp.read(record_size)

            if len(data) < record_size:
                break

            records.append((record_type, data))

    return records


def extract_vertices(data, vertex_size, uv_offset):
    vertices = []
    uvs = []
    num_vertices = len(data) // vertex_size

    for i in range(num_vertices):
        offset = i * vertex_size

        try:
            x, y, z = struct.unpack('<3f', data[offset:offset+12])
            if math.isnan(x) or math.isinf(x): x = 0.0
            if math.isnan(y) or math.isinf(y): y = 0.0
            if math.isnan(z) or math.isinf(z): z = 0.0
        except:
            x, y, z = 0.0, 0.0, 0.0

        u, v = 0.0, 0.0
        if offset + uv_offset + 8 <= len(data):
            try:
                u, v = struct.unpack('<2f', data[offset+uv_offset:offset+uv_offset+8])
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
        idx = struct.unpack('<H', data[i:i+2])[0]
        if idx != 0xFFFF:
            indices.append(idx)
    return indices


def export_model(hnk_path):
    records = read_hunkfile(hnk_path)

    vertex_records = [data for t, data in records if t == 0x40054]
    index_records = [data for t, data in records if t == 0x20055]

    output_dir = os.path.dirname(hnk_path)

    for mesh_idx, (vertex_data, index_data) in enumerate(zip(vertex_records, index_records)):

        if mesh_idx == 0:
            vertex_size = 64
            uv_offset = 12
        else:
            vertex_size = 44
            uv_offset = 12

        vertices, uvs = extract_vertices(vertex_data, vertex_size, uv_offset)
        indices = extract_indices(index_data)

        if not indices:
            continue

        out_file = os.path.join(output_dir, f"mesh_{mesh_idx+1}.obj")

        with open(out_file, 'w') as f:
            f.write(f"o Mesh_{mesh_idx+1}\n")

            for v in vertices:
                f.write(f"v {v[0]:.6f} {v[1]:.6f} {v[2]:.6f}\n")

            for uv in uvs:
                f.write(f"vt {uv[0]:.6f} {uv[1]:.6f}\n")

            for i in range(0, len(indices)-2, 3):
                a, b, c = indices[i], indices[i+1], indices[i+2]
                if a < len(vertices) and b < len(vertices) and c < len(vertices):
                    f.write(f"f {a+1}/{a+1} {b+1}/{b+1} {c+1}/{c+1}\n")


def select_file():
    path = filedialog.askopenfilename(
        title="Select HNK model file",
        filetypes=[("HNK files", "*.hnk"), ("All files", "*.*")]
    )

    if not path:
        return

    try:
        export_model(path)
        messagebox.showinfo("Done", "Model export finished.\n\nOBJ files were saved in the same folder.")
    except Exception as e:
        messagebox.showerror("Error", str(e))


def main():
    root = tk.Tk()
    root.title("HNK Model Extractor")
    root.geometry("420x200")

    label = tk.Label(
        root,
        text="HNK Model Extractor\n\nThis tool is incomplete and still in development.",
        justify="center"
    )
    label.pack(pady=20)

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
