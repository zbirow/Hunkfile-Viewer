import struct
import os
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import numpy as np
from OpenGL.GL import *
from OpenGL.GLU import *
from OpenGL.GLUT import *
import pyopengltk as opengl

# --- Pomocnicze ---
def read_f32(data, offset, endian="<"):
    return struct.unpack(endian+"f", data[offset:offset+4])[0]

def split_submeshes(index_data, endian="<"):
    submeshes = []
    current = []
    for i in range(0, len(index_data), 2):
        idx = struct.unpack(endian+"H", index_data[i:i+2])[0]
        if idx == 0xFFFF:
            if current:
                submeshes.append(current)
                current = []
        else:
            current.append(idx)
    if current:
        submeshes.append(current)
    return submeshes

def remap_indices(indices, vertex_mapping):
    """Przemapowuje indeksy używając podanego mapowania starych->nowych indeksów"""
    remapped = []
    for idx in indices:
        if idx in vertex_mapping:
            remapped.append(vertex_mapping[idx])
    return remapped

def extract_model_data(vertex_data, index_data, vertex_stride, uv_offset, vertex_offset, index_offset,
                      start_vertex, vertex_count, step_vertex, endian="<", unit=1.0):
    """Wyciąga dane modelu do wyświetlenia"""
    
    vertex_data = vertex_data[vertex_offset:]
    index_data = index_data[index_offset:]
    submeshes = split_submeshes(index_data, endian)
    
    total_vertices = len(vertex_data) // vertex_stride
    
    # Wybierz które wierzchołki będą użyte
    if vertex_count > 0:
        # Jeśli podano konkretną liczbę, weź tylko tyle wierzchołków
        end_vertex = min(start_vertex + vertex_count, total_vertices)
        selected_vertices = list(range(start_vertex, end_vertex, step_vertex))
    else:
        # Jeśli vertex_count = 0, weź wszystkie od start_vertex
        selected_vertices = list(range(start_vertex, total_vertices, step_vertex))
    
    if not selected_vertices:
        return None, None, None
    
    # Stwórz mapowanie starych indeksów na nowe
    vertex_mapping = {old_idx: new_idx for new_idx, old_idx in enumerate(selected_vertices)}
    
    # Pobierz dane wierzchołków
    vertices = []
    for old_idx in selected_vertices:
        base_offset = old_idx * vertex_stride
        x = read_f32(vertex_data, base_offset+0, endian) * unit
        y = read_f32(vertex_data, base_offset+4, endian) * unit
        z = read_f32(vertex_data, base_offset+8, endian) * unit
        vertices.append([x, y, z])
    
    # Filtruj i przemapuj indeksy dla każdego submesha
    all_indices = []
    for indices in submeshes:
        remapped = remap_indices(indices, vertex_mapping)
        if len(remapped) >= 3:
            all_indices.extend(remapped)
    
    if not all_indices:
        return None, None, None
    
    return np.array(vertices, dtype=np.float32), np.array(all_indices, dtype=np.int32)

# Klasa do wyświetlania OpenGL
class ModelViewer(opengl.OpenGLFrame):
    def __init__(self, master=None, **kwargs):
        super().__init__(master, **kwargs)
        self.vertices = None
        self.indices = None
        self.rotation_x = 0
        self.rotation_y = 0
        self.last_x = 0
        self.last_y = 0
        self.dragging = False
        self.scale = 1.0
        self.translate = [0, 0, -3]
        self.bg_color = [0.2, 0.2, 0.2, 1.0]
        self.wireframe = False
        
        # Bind mouse events
        self.bind("<Button-1>", self.on_mouse_down)
        self.bind("<B1-Motion>", self.on_mouse_drag)
        self.bind("<ButtonRelease-1>", self.on_mouse_up)
        self.bind("<MouseWheel>", self.on_mouse_wheel)
        
    def initgl(self):
        """Inicjalizacja OpenGL"""
        glClearColor(*self.bg_color)
        glEnable(GL_DEPTH_TEST)
        glEnable(GL_LIGHTING)
        glEnable(GL_LIGHT0)
        glEnable(GL_COLOR_MATERIAL)
        glColorMaterial(GL_FRONT_AND_BACK, GL_AMBIENT_AND_DIFFUSE)
        
        # Ustawienia światła
        glLightfv(GL_LIGHT0, GL_POSITION, [1.0, 2.0, 3.0, 0.0])
        glLightfv(GL_LIGHT0, GL_AMBIENT, [0.3, 0.3, 0.3, 1.0])
        glLightfv(GL_LIGHT0, GL_DIFFUSE, [1.0, 1.0, 1.0, 1.0])
        
        # Ustawienia widoku
        glMatrixMode(GL_PROJECTION)
        gluPerspective(45, self.width/self.height, 0.1, 100.0)
        glMatrixMode(GL_MODELVIEW)
        
    def redraw(self):
        """Rysowanie sceny"""
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        glLoadIdentity()
        
        # Ustaw kamerę
        glTranslatef(*self.translate)
        glRotatef(self.rotation_x, 1, 0, 0)
        glRotatef(self.rotation_y, 0, 1, 0)
        glScalef(self.scale, self.scale, self.scale)
        
        # Rysuj siatkę pomocniczą
        self.draw_grid()
        
        # Rysuj model
        if self.vertices is not None and len(self.vertices) > 0:
            if self.wireframe:
                glPolygonMode(GL_FRONT_AND_BACK, GL_LINE)
                glDisable(GL_LIGHTING)
                glColor3f(0.8, 0.8, 1.0)
            else:
                glPolygonMode(GL_FRONT_AND_BACK, GL_FILL)
                glEnable(GL_LIGHTING)
                glColor3f(0.6, 0.6, 0.9)
            
            glEnableClientState(GL_VERTEX_ARRAY)
            glVertexPointerf(self.vertices)
            
            if self.indices is not None:
                glDrawElements(GL_TRIANGLES, len(self.indices), GL_UNSIGNED_INT, self.indices)
            
            glDisableClientState(GL_VERTEX_ARRAY)
            
            # Resetuj tryb rysowania
            glPolygonMode(GL_FRONT_AND_BACK, GL_FILL)
            glEnable(GL_LIGHTING)
        
        self.tkSwapBuffers()
    
    def draw_grid(self):
        """Rysuje siatkę pomocniczą"""
        glDisable(GL_LIGHTING)
        glBegin(GL_LINES)
        
        # Siatka na podłodze
        glColor3f(0.3, 0.3, 0.3)
        size = 2.0
        steps = 10
        for i in range(-steps, steps + 1):
            x = size * i / steps
            glVertex3f(x, 0, -size)
            glVertex3f(x, 0, size)
            glVertex3f(-size, 0, x)
            glVertex3f(size, 0, x)
        
        # Osie
        glColor3f(1, 0, 0)  # X - czerwony
        glVertex3f(0, 0, 0)
        glVertex3f(size, 0, 0)
        
        glColor3f(0, 1, 0)  # Y - zielony
        glVertex3f(0, 0, 0)
        glVertex3f(0, size, 0)
        
        glColor3f(0, 0, 1)  # Z - niebieski
        glVertex3f(0, 0, 0)
        glVertex3f(0, 0, size)
        
        glEnd()
        glEnable(GL_LIGHTING)
    
    def set_model(self, vertices, indices):
        """Ustawia model do wyświetlenia"""
        self.vertices = vertices
        self.indices = indices
        self.calculate_scale()
        self.redraw()
    
    def calculate_scale(self):
        """Oblicza skalę na podstawie rozmiaru modelu"""
        if self.vertices is not None and len(self.vertices) > 0:
            min_coords = np.min(self.vertices, axis=0)
            max_coords = np.max(self.vertices, axis=0)
            size = np.max(max_coords - min_coords)
            if size > 0:
                self.scale = 2.0 / size
                # Wyśrodkuj model
                center = (min_coords + max_coords) / 2
                self.translate = [-center[0], -center[1], -3]
    
    def on_mouse_down(self, event):
        self.dragging = True
        self.last_x = event.x
        self.last_y = event.y
    
    def on_mouse_drag(self, event):
        if self.dragging:
            dx = event.x - self.last_x
            dy = event.y - self.last_y
            self.rotation_y += dx * 0.5
            self.rotation_x += dy * 0.5
            self.last_x = event.x
            self.last_y = event.y
            self.redraw()
    
    def on_mouse_up(self, event):
        self.dragging = False
    
    def on_mouse_wheel(self, event):
        self.scale *= 1.1 ** (event.delta / 120)
        self.redraw()

# --- Główna aplikacja ---
class VertexIndexExporter:
    def __init__(self, root):
        self.root = root
        self.root.title("Vertex/Index OBJ Exporter with 3D Preview")
        
        self.vertex_path = ""
        self.index_path = ""
        self.last_output_dir = ""
        
        # Zmienne tkinter
        self.stride_val = tk.IntVar(value=64)
        self.uv_offset_val = tk.IntVar(value=24)
        self.unit_val = tk.DoubleVar(value=1.0)
        self.endian_val = tk.StringVar(value="<")
        self.vertex_offset_val = tk.IntVar(value=0)
        self.index_offset_val = tk.IntVar(value=0)
        self.start_vertex_val = tk.IntVar(value=0)
        self.vertex_count_val = tk.IntVar(value=0)  # 0 = wszystkie
        self.step_vertex_val = tk.IntVar(value=1)
        self.export_residual_val = tk.BooleanVar(value=False)
        self.auto_save_val = tk.BooleanVar(value=True)
        
        self.setup_ui()
        self.setup_bindings()
    
    def setup_ui(self):
        # Główny podział na lewą (kontrolki) i prawą (podgląd) część
        main_paned = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        main_paned.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Lewy panel - kontrolki
        left_frame = ttk.Frame(main_paned)
        main_paned.add(left_frame, weight=1)
        
        # Prawy panel - podgląd 3D
        right_frame = ttk.Frame(main_paned)
        main_paned.add(right_frame, weight=2)
        
        self.setup_controls(left_frame)
        self.setup_preview(right_frame)
    
    def setup_controls(self, parent):
        # Pliki
        file_frame = ttk.LabelFrame(parent, text="Files", padding=5)
        file_frame.pack(fill="x", pady=5)
        
        ttk.Button(file_frame, text="Load vertex.bin", command=self.load_vertex).pack(fill="x")
        self.vertex_label = ttk.Label(file_frame, text="No file")
        self.vertex_label.pack()
        
        ttk.Button(file_frame, text="Load index.bin", command=self.load_index).pack(fill="x", pady=(5,0))
        self.index_label = ttk.Label(file_frame, text="No file")
        self.index_label.pack()
        
        # Automatyczne zapisywanie
        auto_frame = ttk.Frame(file_frame)
        auto_frame.pack(fill="x", pady=5)
        ttk.Checkbutton(auto_frame, text="Auto-save", 
                       variable=self.auto_save_val).pack(side=tk.LEFT)
        self.output_preview_label = ttk.Label(auto_frame, text="Preview: -", foreground="blue")
        self.output_preview_label.pack(side=tk.LEFT, padx=10)
        
        # Parametry
        params_frame = ttk.LabelFrame(parent, text="Parameters", padding=5)
        params_frame.pack(fill="x", pady=5)
        
        # Grid dla parametrów
        params = [
            ("Vertex stride:", self.stride_val),
            ("UV offset:", self.uv_offset_val),
            ("Vertex offset:", self.vertex_offset_val),
            ("Index offset:", self.index_offset_val),
            ("Start vertex:", self.start_vertex_val),
            ("Vertex count (0=all):", self.vertex_count_val),
            ("Step (co ile):", self.step_vertex_val),
            ("Unit scale:", self.unit_val),
            ("Endian:", self.endian_val)
        ]
        
        for i, (label, var) in enumerate(params):
            ttk.Label(params_frame, text=label).grid(row=i, column=0, sticky='w', pady=2)
            ttk.Entry(params_frame, textvariable=var, width=15).grid(row=i, column=1, padx=5, pady=2)
        
        # Informacje
        info_frame = ttk.LabelFrame(parent, text="Info", padding=5)
        info_frame.pack(fill="x", pady=5)
        
        self.max_vertex_label = ttk.Label(info_frame, text="Max vertices: -")
        self.max_vertex_label.pack(anchor='w')
        
        self.preview_label = ttk.Label(info_frame, text="Wybrane: -")
        self.preview_label.pack(anchor='w')
        
        ttk.Checkbutton(info_frame, text="Eksportuj resztkowe modele", 
                       variable=self.export_residual_val).pack(anchor='w', pady=5)
        
        # Przyciski
        button_frame = ttk.Frame(parent)
        button_frame.pack(pady=10)
        
        ttk.Button(button_frame, text="Detect Layout", command=self.detect_layout, width=12).pack(side=tk.LEFT, padx=2)
        ttk.Button(button_frame, text="Update Preview", command=self.update_preview, width=12).pack(side=tk.LEFT, padx=2)
        ttk.Button(button_frame, text="Export OBJ", command=self.run_export, width=12).pack(side=tk.LEFT, padx=2)
        
        # Text output
        ttk.Label(parent, text="Log:").pack(anchor='w')
        self.output_text = tk.Text(parent, height=8, width=40)
        self.output_text.pack(fill="both", expand=True, pady=5)
        
        # Scrollbar dla text output
        scrollbar = ttk.Scrollbar(self.output_text)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.output_text.config(yscrollcommand=scrollbar.set)
        scrollbar.config(command=self.output_text.yview)
    
    def setup_preview(self, parent):
        # Ramka podglądu
        preview_frame = ttk.LabelFrame(parent, text="3D Preview", padding=5)
        preview_frame.pack(fill="both", expand=True)
        
        # Pasek narzędzi podglądu
        toolbar = ttk.Frame(preview_frame)
        toolbar.pack(fill="x", pady=(0, 5))
        
        ttk.Button(toolbar, text="Reset View", command=self.reset_view).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="Wireframe", command=self.toggle_wireframe).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="Refresh", command=self.update_preview).pack(side=tk.LEFT, padx=2)
        
        # Viewer OpenGL
        self.viewer = ModelViewer(preview_frame, width=600, height=500)
        self.viewer.pack(fill="both", expand=True)
    
    def setup_bindings(self):
        self.stride_val.trace_add('write', lambda *args: [self.update_max_vertex_count(), self.update_output_preview()])
        self.vertex_offset_val.trace_add('write', self.update_max_vertex_count)
        self.start_vertex_val.trace_add('write', lambda *args: [self.update_max_vertex_count(), self.update_output_preview()])
        self.vertex_count_val.trace_add('write', lambda *args: [self.update_max_vertex_count(), self.update_output_preview()])
        self.step_vertex_val.trace_add('write', lambda *args: [self.update_max_vertex_count(), self.update_output_preview()])
        self.auto_save_val.trace_add('write', self.update_output_preview)
    
    def load_vertex(self):
        self.vertex_path = filedialog.askopenfilename(filetypes=[("BIN files","*.bin"),("All files","*.*")])
        self.vertex_label.config(text=os.path.basename(self.vertex_path) if self.vertex_path else "No file")
        self.update_max_vertex_count()
        self.update_output_preview()
        self.update_preview()
    
    def load_index(self):
        self.index_path = filedialog.askopenfilename(filetypes=[("BIN files","*.bin"),("All files","*.*")])
        self.index_label.config(text=os.path.basename(self.index_path) if self.index_path else "No file")
        self.update_preview()
    
    def update_max_vertex_count(self):
        if self.vertex_path and self.stride_val.get() > 0:
            try:
                with open(self.vertex_path,"rb") as f:
                    data = f.read()
                data = data[self.vertex_offset_val.get():]
                max_vertices = len(data) // self.stride_val.get()
                self.max_vertex_label.config(text=f"Max vertices: {max_vertices}")
                
                start = self.start_vertex_val.get()
                count = self.vertex_count_val.get()
                step = self.step_vertex_val.get()
                
                if count > 0:
                    end = min(start + count, max_vertices)
                    selected = len(range(start, end, step))
                    self.preview_label.config(
                        text=f"Wybrane: {selected} vertexów (od {start} do {end-1})"
                    )
                else:
                    selected = len(range(start, max_vertices, step))
                    self.preview_label.config(
                        text=f"Wybrane: {selected} vertexów (od {start} do {max_vertices-1})"
                    )
            except Exception as e:
                self.max_vertex_label.config(text="Max vertices: -")
                self.preview_label.config(text="Wybrane: -")
        else:
            self.max_vertex_label.config(text="Max vertices: -")
            self.preview_label.config(text="Wybrane: -")
    
    def update_output_preview(self, *args):
        if self.vertex_path and self.auto_save_val.get():
            base_name = os.path.splitext(os.path.basename(self.vertex_path))[0]
            start = self.start_vertex_val.get()
            count = self.vertex_count_val.get()
            step = self.step_vertex_val.get()
            
            if step > 1 or count > 0:
                preview = f"{base_name}_start{start}"
                if count > 0:
                    preview += f"_count{count}"
                if step > 1:
                    preview += f"_step{step}"
                preview += ".obj"
            else:
                preview = f"{base_name}.obj"
            
            self.output_preview_label.config(text=f"Preview: {preview}")
        else:
            self.output_preview_label.config(text="Preview: -")
    
    def update_preview(self):
        """Aktualizuje podgląd 3D"""
        if not self.vertex_path or not self.index_path:
            self.log("Wczytaj pliki vertex i index")
            return
        
        try:
            with open(self.vertex_path,"rb") as f:
                vertex_data = f.read()
            with open(self.index_path,"rb") as f:
                index_data = f.read()
            
            # Walidacja parametrów
            max_vertices = len(vertex_data[self.vertex_offset_val.get():]) // self.stride_val.get()
            
            if max_vertices == 0:
                self.log("Brak vertexów do wyświetlenia")
                return
            
            if self.start_vertex_val.get() >= max_vertices:
                self.log(f"Start vertex ({self.start_vertex_val.get()}) przekracza maksimum ({max_vertices})")
                return
            
            # Wyciągnij dane modelu
            vertices, indices = extract_model_data(
                vertex_data, index_data, self.stride_val.get(), self.uv_offset_val.get(),
                self.vertex_offset_val.get(), self.index_offset_val.get(),
                self.start_vertex_val.get(), self.vertex_count_val.get(), self.step_vertex_val.get(),
                self.endian_val.get(), self.unit_val.get()
            )
            
            if vertices is not None and indices is not None:
                self.viewer.set_model(vertices, indices)
                self.log(f"Załadowano model: {len(vertices)} vertexów, {len(indices)//3} trójkątów")
            else:
                self.log("Nie udało się załadować modelu - sprawdź parametry")
                
        except Exception as e:
            self.log(f"Błąd ładowania modelu: {str(e)}")
    
    def reset_view(self):
        self.viewer.rotation_x = 0
        self.viewer.rotation_y = 0
        self.viewer.translate = [0, 0, -3]
        if self.viewer.vertices is not None:
            self.viewer.calculate_scale()
        self.viewer.redraw()
    
    def toggle_wireframe(self):
        self.viewer.wireframe = not self.viewer.wireframe
        self.viewer.redraw()
    
    def log(self, message):
        self.output_text.insert(tk.END, message + "\n")
        self.output_text.see(tk.END)
    
    def run_export(self):
        if not self.vertex_path or not self.index_path:
            messagebox.showerror("Error","Select vertex and index files")
            return
        
        try:
            with open(self.vertex_path,"rb") as f:
                vertex_data = f.read()
            with open(self.index_path,"rb") as f:
                index_data = f.read()
            
            max_vertices = len(vertex_data[self.vertex_offset_val.get():]) // self.stride_val.get()
            
            if max_vertices == 0:
                messagebox.showerror("Error", "No vertices to export")
                return
            
            if self.start_vertex_val.get() >= max_vertices:
                messagebox.showerror("Error", 
                    f"Start vertex ({self.start_vertex_val.get()}) przekracza maksymalną liczbę ({max_vertices})")
                return
            
            # Generuj bazową ścieżkę wyjściową
            if self.auto_save_val.get():
                base_name = os.path.splitext(os.path.basename(self.vertex_path))[0]
                if self.last_output_dir:
                    output_dir = self.last_output_dir
                else:
                    output_dir = os.path.dirname(self.vertex_path)
                
                base_output = os.path.join(output_dir, base_name)
            else:
                base_output = filedialog.asksaveasfilename(defaultextension=".obj")
                if not base_output:
                    return
                self.last_output_dir = os.path.dirname(base_output)
                base_output = os.path.splitext(base_output)[0]
            
            # Eksportuj
            success, result = export_obj_filtered(
                vertex_data, index_data, self.stride_val.get(), self.uv_offset_val.get(),
                self.vertex_offset_val.get(), self.index_offset_val.get(),
                self.start_vertex_val.get(), self.vertex_count_val.get(), self.step_vertex_val.get(),
                base_output, self.endian_val.get(), self.unit_val.get()
            )
            
            if success:
                messagebox.showinfo("Done", f"Export finished: {os.path.basename(result)}")
            else:
                messagebox.showerror("Error", result)
                
        except Exception as e:
            messagebox.showerror("Error", f"Export failed: {str(e)}")
    
    def detect_layout(self):
        if not self.vertex_path:
            messagebox.showerror("Error","Select vertex file first")
            return
        try:
            with open(self.vertex_path,"rb") as f:
                data = f.read()
            possible_strides = [32,36,40,44,48,52,56,60,64,68,72]
            self.output_text.delete(1.0, tk.END)
            self.output_text.insert(tk.END,"Possible vertex strides and UV offsets:\n")
            self.output_text.insert(tk.END,"-" * 60 + "\n")
            found = False
            for stride in possible_strides:
                if len(data) % stride != 0:
                    continue
                found = True
                vertex_count = len(data) // stride
                uv_candidates = []
                for off in range(8, stride-4, 4):
                    try:
                        u = read_f32(data, off)
                        v = read_f32(data, off+4)
                        if -10 < u < 10 and -10 < v < 10:
                            uv_candidates.append(off)
                    except:
                        continue
                self.output_text.insert(tk.END,f"Stride: {stride} (vertices: {vertex_count}) -> UV offsets: {uv_candidates}\n")
            if not found:
                self.output_text.insert(tk.END,"No matching strides found\n")
        except Exception as e:
            self.output_text.insert(tk.END,f"Error: {str(e)}\n")

def export_obj_filtered(vertex_data, index_data, vertex_stride, uv_offset, vertex_offset, index_offset,
                       start_vertex, vertex_count, step_vertex, output_path, endian="<", unit=1.0):
    """Eksportuje wybrane wierzchołki"""
    
    vertex_data = vertex_data[vertex_offset:]
    index_data = index_data[index_offset:]
    submeshes = split_submeshes(index_data, endian)
    
    total_vertices = len(vertex_data) // vertex_stride
    
    # Wybierz które wierzchołki będą eksportowane
    if vertex_count > 0:
        end_vertex = min(start_vertex + vertex_count, total_vertices)
        selected_vertices = list(range(start_vertex, end_vertex, step_vertex))
    else:
        selected_vertices = list(range(start_vertex, total_vertices, step_vertex))
    
    if not selected_vertices:
        return False, "No vertices selected"
    
    # Stwórz mapowanie starych indeksów na nowe
    vertex_mapping = {old_idx: new_idx for new_idx, old_idx in enumerate(selected_vertices)}
    
    # Filtruj i przemapuj indeksy dla każdego submesha
    filtered_submeshes = []
    for indices in submeshes:
        remapped = remap_indices(indices, vertex_mapping)
        if len(remapped) >= 3:
            filtered_submeshes.append(remapped)
    
    if not filtered_submeshes:
        return False, "No valid submeshes after filtering"
    
    # Generuj nazwę pliku
    base, ext = os.path.splitext(output_path)
    if step_vertex > 1 or vertex_count > 0:
        filename = f"{base}_start{start_vertex}"
        if vertex_count > 0:
            filename += f"_count{vertex_count}"
        if step_vertex > 1:
            filename += f"_step{step_vertex}"
        output_path = filename + ext
    else:
        output_path = f"{base}{ext}"
    
    with open(output_path, "w") as f:
        for sm_idx, indices in enumerate(filtered_submeshes):
            f.write(f"o Submesh_{sm_idx+1}\n")
            
            # Eksportuj tylko wybrane wierzchołki
            for new_idx, old_idx in enumerate(selected_vertices):
                base_offset = old_idx * vertex_stride
                x = read_f32(vertex_data, base_offset+0, endian) * unit
                y = read_f32(vertex_data, base_offset+4, endian) * unit
                z = read_f32(vertex_data, base_offset+8, endian) * unit
                f.write(f"v {x:.6f} {y:.6f} {z:.6f}\n")
                
                # UV
                u = read_f32(vertex_data, base_offset+uv_offset, endian)
                v = read_f32(vertex_data, base_offset+uv_offset+4, endian)
                f.write(f"vt {u:.6f} {1.0-v:.6f}\n")
            
            # Eksportuj przemapowane twarze
            for i in range(0, len(indices)-2, 3):
                a,b,c = indices[i], indices[i+1], indices[i+2]
                f.write(f"f {a+1}/{a+1} {b+1}/{b+1} {c+1}/{c+1}\n")
    
    return True, output_path

# Uruchomienie aplikacji
if __name__ == "__main__":
    root = tk.Tk()
    app = VertexIndexExporter(root)
    root.geometry("1200x700")
    root.mainloop()