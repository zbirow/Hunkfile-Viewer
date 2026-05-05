import sys
import struct
import numpy as np
from PyQt5 import QtWidgets, QtCore
import pyqtgraph.opengl as gl

# =======================================================
# CONFIGURATIONS
# =======================================================

# 1. MATRIX_MODE: "LOCAL" lub "INVERSE_BIND"
# "LOCAL" - macierze lokalne, mnożymy przez rodzica (najczęstsze)
# "INVERSE_BIND" - macierze odwrotne bazy, wystarczy je odwrócić, nie mnożymy przez rodzica!
MATRIX_MODE = "LOCAL"

# 2. MULTIPLY_ORDER: Wpływa tylko jeśli MATRIX_MODE = "LOCAL"
# Opcja 1: world[p] @ mat (DirectX / Row-major - typowe dla starych gier PC/Xbox)
# Opcja 2: mat @ world[p] (OpenGL / Column-major - typowe dla GameCube/PS2/Wii)
MULTIPLY_ORDER = 2

# 3. TRANSLATION_ROW: Gdzie znajduje się pozycja (X, Y, Z) w macierzy 4x4?
# True: wiersz 3 (mat[3,0:3]) - standard w DirectX
# False: kolumna 3 (mat[0:3,3]) - standard w OpenGL
TRANSLATION_ROW = True 

ROTATE_X = 45  # Obrót wokół osi X w stopniach
ROTATE_Y = 0   # Obrót wokół osi Y w stopniach
ROTATE_Z = 135   # Obrót wokół osi Z w stopniach

# =========================
# UTILS
# =========================

def is_finite_matrix(m):
    return np.all(np.isfinite(m)) and np.max(np.abs(m)) < 1e6

def score_matrix(raw):
    score = 0
    if abs(raw[3]) < 1e-3: score += 1
    if abs(raw[7]) < 1e-3: score += 1
    if abs(raw[11]) < 1e-3: score += 1
    if abs(raw[15] - 1.0) < 1e-3: score += 2
    return score

def get_rotation_matrix(rx_deg, ry_deg, rz_deg):
    rx = np.radians(rx_deg)
    ry = np.radians(ry_deg)
    rz = np.radians(rz_deg)

    Rx = np.array([
        [1, 0, 0],
        [0, np.cos(rx), -np.sin(rx)],
        [0, np.sin(rx), np.cos(rx)]
    ])
    Ry = np.array([
        [np.cos(ry), 0, np.sin(ry)],
        [0, 1, 0],
        [-np.sin(ry), 0, np.cos(ry)]
    ])
    Rz = np.array([
        [np.cos(rz), -np.sin(rz), 0],
        [np.sin(rz), np.cos(rz), 0],
        [0, 0, 1]
    ])

    return Rz @ Ry @ Rx
# =========================
# PARSER
# =========================

def extract_bone_names(chunk):
    root_idx = chunk.find(b'x_root\x00')
    if root_idx == -1:
        return [], -1

    bones = []
    pos = root_idx

    while pos < len(chunk):
        end = chunk.find(b'\x00', pos)
        if end == -1:
            break

        raw = chunk[pos:end]
        if not raw or not all(32 <= b <= 126 for b in raw):
            break

        name = raw.decode('ascii', errors='ignore')
        if name == "Mesh":
            break

        bones.append(name)
        pos = end + 1

    return bones, root_idx

def find_parent_array(chunk, num_bones):
    size = num_bones * 2
    for i in range(len(chunk) - size):
        try:
            vals = struct.unpack('<' + 'h'*num_bones, chunk[i:i+size])
        except:
            continue

        if vals[0] != -1:
            continue

        if all(-1 <= v < num_bones for v in vals):
            return list(vals)

    return [-1]*num_bones

# =========================
# MATRIX DETECTION & EXTRACTION
# =========================

def find_matrix_block(chunk, num_bones):
    block_size = num_bones * 64
    best_score = -1
    best_offset = -1

    for i in range(0, len(chunk) - block_size, 16):
        valid = 0
        score_sum = 0

        for j in range(num_bones):
            off = i + j*64
            try:
                raw = struct.unpack('<16f', chunk[off:off+64])
            except:
                continue

            mat = np.array(raw).reshape(4,4)
            if not is_finite_matrix(mat):
                continue

            s = score_matrix(raw)
            if s >= 3:
                valid += 1
                score_sum += s

        if valid > num_bones * 0.6:
            if score_sum > best_score:
                best_score = score_sum
                best_offset = i

    print(f"Znaleziono blok macierzy pod offsetem: {best_offset}")
    return best_offset

def extract_matrices(chunk, num_bones):
    start = find_matrix_block(chunk, num_bones)

    if start == -1:
        print("❌ brak macierzy")
        return [np.eye(4)] * num_bones

    mats = []
    for i in range(num_bones):
        off = start + i*64
        try:
            raw = struct.unpack('<16f', chunk[off:off+64])
            mat = np.array(raw, dtype=np.float32).reshape(4,4)
            mats.append(mat)
        except:
            mats.append(np.eye(4))

    return mats

# =========================
# FORWARD KINEMATICS
# =========================

def build_world_positions(raw_mats, parents):
    world = [None] * len(raw_mats)

    for i in range(len(raw_mats)):
        mat = raw_mats[i]

        if mat is None or not is_finite_matrix(mat):
            mat = np.eye(4)

        if MATRIX_MODE == "INVERSE_BIND":
            # Jeśli to macierze Inverse Bind, po prostu je odwracamy. Brak dziedziczenia.
            try:
                world[i] = np.linalg.inv(mat)
            except:
                world[i] = np.eye(4)
        else:
            # MATRIX_MODE == "LOCAL" - mnożymy zgodnie z hierarchią
            p = parents[i]
            if p == -1 or world[p] is None:
                world[i] = mat
            else:
                if MULTIPLY_ORDER == 1:
                    world[i] = world[p] @ mat
                else:
                    world[i] = mat @ world[p]

    positions = []
    for m in world:
        if m is None or not is_finite_matrix(m):
            positions.append((0,0,0))
        else:
            if TRANSLATION_ROW:
                positions.append((m[3,0], m[3,1], m[3,2]))
            else:
                positions.append((m[0,3], m[1,3], m[2,3]))

    positions = np.array(positions)

    # normalizacja rozmiaru
    if len(positions) > 0:
        center = np.nanmean(positions, axis=0)
        positions -= center
        scale = np.nanmax(np.linalg.norm(positions, axis=1))
        if scale > 0:
            positions /= scale

        # --- NOWY KOD - OBRÓT GLOBALNY ---
        rot_mat = get_rotation_matrix(ROTATE_X, ROTATE_Y, ROTATE_Z)
        positions = positions @ rot_mat.T 
        # ---------------------------------

    return positions

# =========================
# MAIN PARSE
# =========================

def parse_hnk(data):
    import re
    results = {}
    pattern = re.compile(b'RenderModelTemplate\x00(.*?)\x00+(....)\x50\x10\x10\x00', re.DOTALL)

    for i, m in enumerate(pattern.finditer(data)):
        name = m.group(1).decode('ascii', errors='ignore').strip()
        size = int.from_bytes(m.group(2), 'little')
        start = m.end()
        chunk = data[start:start+size]

        if not name:
            scene_idx = chunk.find(b'\x00scene')
            if scene_idx != -1:
                s_idx = scene_idx - 1
                while s_idx >= 0 and 32 <= chunk[s_idx] <= 126:
                    s_idx -= 1
                name = chunk[s_idx+1:scene_idx].decode('ascii', errors='ignore')
        
        if not name:
            name = f"Skeleton_{i+1}"

        # Upewnienie się że nazwa na liście będzie unikalna
        unique_name = name
        counter = 1
        while unique_name in results:
            unique_name = f"{name}_{counter}"
            counter += 1

        bones, _ = extract_bone_names(chunk)
        if not bones:
            continue

        parents = find_parent_array(chunk, len(bones))
        raw_mats = extract_matrices(chunk, len(bones))
        positions = build_world_positions(raw_mats, parents)

        results[unique_name] = {
            "bones": bones,
            "parents": parents,
            "positions": positions
        }

    return results

# =========================
# VIEWER
# =========================

class Viewer(gl.GLViewWidget):
    def __init__(self):
        super().__init__()
        self.setCameraPosition(distance=3)
        self.setBackgroundColor((30,30,30,255))
        grid = gl.GLGridItem()
        grid.scale(1,1,1)
        self.addItem(grid)
        self.items = []

    def clear_scene(self):
        for it in self.items:
            self.removeItem(it)
        self.items = []

    def draw(self, skeleton):
        self.clear_scene()
        pos = skeleton["positions"]
        parents = skeleton["parents"]

        pts = gl.GLScatterPlotItem(pos=pos, size=6, color=(0.2,0.7,1,1))
        self.addItem(pts)
        self.items.append(pts)

        if len(pos) > 0:
            root = gl.GLScatterPlotItem(pos=np.array([pos[0]]), size=10, color=(1,0.2,0.2,1))
            self.addItem(root)
            self.items.append(root)

        for i, p in enumerate(parents):
            if 0 <= p < len(pos):
                line = gl.GLLinePlotItem(
                    pos=np.array([pos[i], pos[p]]),
                    color=(1,1,1,1),
                    width=2,
                    antialias=True
                )
                self.addItem(line)
                self.items.append(line)

# =========================
# APP & GUI HANDLERS
# =========================

class App(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("HNK Skeleton Viewer PC")
        self.resize(1200, 800)

        # Tworzenie widgetu bazowego i layoutu z panelem bocznym
        central_widget = QtWidgets.QWidget()
        self.setCentralWidget(central_widget)
        layout = QtWidgets.QHBoxLayout(central_widget)
        layout.setContentsMargins(0, 0, 0, 0)

        splitter = QtWidgets.QSplitter(QtCore.Qt.Horizontal)
        layout.addWidget(splitter)

        # Lewy panel: Lista modeli
        self.list_widget = QtWidgets.QListWidget()
        self.list_widget.setMinimumWidth(200)
        splitter.addWidget(self.list_widget)

        # Prawy panel: Twój oryginalny widok z 3D
        self.viewer = Viewer()
        splitter.addWidget(self.viewer)

        splitter.setSizes([250, 950])

        # Zdarzenie po kliknięciu elementu na liście
        self.list_widget.currentItemChanged.connect(self.on_item_selected)

        self.skeletons = {}
        self.load_file()

    def load_file(self):
        path, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Open HNK", "", "*.hnk")
        if not path:
            return

        with open(path, "rb") as f:
            data = f.read()

        self.skeletons = parse_hnk(data)
        self.list_widget.clear()

        if not self.skeletons:
            print("❌ no skeletons found in the file.")
            return

        # Ładowanie nazw do listy
        for name in self.skeletons.keys():
            self.list_widget.addItem(name)

        # Rysowanie pierwszego domyślnie
        self.list_widget.setCurrentRow(0)

    def on_item_selected(self, current, previous):
        if current is None:
            return
            
        name = current.text()
        if name in self.skeletons:
            self.viewer.draw(self.skeletons[name])

if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    win = App()
    win.show()
    sys.exit(app.exec_())
