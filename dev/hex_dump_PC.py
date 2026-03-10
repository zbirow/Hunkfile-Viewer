import struct
import os
import tkinter as tk
from tkinter import filedialog, messagebox


PC_VERTEX = 0x40054
PC_INDEX = 0x20055

WII_VERTEX = 0x202031
WII_INDEX = 0x202032


def read_hnk(path):

    records = []

    with open(path, "rb") as f:

        while True:

            size_bytes = f.read(4)
            if not size_bytes:
                break

            type_bytes = f.read(4)
            if not type_bytes:
                break

            size = struct.unpack("<I", size_bytes)[0]
            rtype = struct.unpack("<I", type_bytes)[0]

            data = f.read(size)

            if len(data) < size:
                break

            records.append((rtype, data))

    return records


def detect_platform(records):

    for t, _ in records:

        if t in (WII_VERTEX, WII_INDEX):
            return "Wii"

    return "PC"


def dump_chunks(path):

    records = read_hnk(path)

    platform = detect_platform(records)

    if platform == "PC":
        vertex_id = PC_VERTEX
        index_id = PC_INDEX
    else:
        vertex_id = WII_VERTEX
        index_id = WII_INDEX

    print("Detected platform:", platform)

    output_dir = os.path.dirname(path)

    vcount = 1
    icount = 1

    for rtype, data in records:

        if rtype == vertex_id:

            out = os.path.join(output_dir, f"vertex_{vcount}.bin")

            with open(out, "wb") as f:
                f.write(data)

            print("Saved:", out)

            vcount += 1


        elif rtype == index_id:

            out = os.path.join(output_dir, f"index_{icount}.bin")

            with open(out, "wb") as f:
                f.write(data)

            print("Saved:", out)

            icount += 1


def select_file():

    path = filedialog.askopenfilename(
        title="Select HNK / DAT file",
        filetypes=[
            ("Model files", "*.hnk *.dat"),
            ("All files", "*.*")
        ]
    )

    if not path:
        return

    try:

        dump_chunks(path)

        messagebox.showinfo(
            "Done",
            "Vertex and Index chunks dumped."
        )

    except Exception as e:

        messagebox.showerror("Error", str(e))


def main():

    root = tk.Tk()
    root.title("HNK Chunk Dumper")
    root.geometry("380x160")

    label = tk.Label(
        root,
        text="Dump Vertex / Index chunks\nfrom HNK / DAT files",
        justify="center"
    )

    label.pack(pady=30)

    btn = tk.Button(
        root,
        text="Select File",
        width=20,
        command=select_file
    )

    btn.pack(pady=10)

    root.mainloop()


if __name__ == "__main__":
    main()