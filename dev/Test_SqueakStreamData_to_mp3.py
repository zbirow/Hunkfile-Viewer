import os
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from pydub import AudioSegment

class GameAudioExtractorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Ekstraktor Audio (RAWI / Embedded) do MP3")
        self.root.geometry("550x550")
        self.root.configure(padx=20, pady=20)

        # Zakładki (Tabs) do obsługi dwóch różnych formatów
        self.notebook = ttk.Notebook(root)
        self.notebook.pack(expand=True, fill="both")

        self.tab1 = ttk.Frame(self.notebook)
        self.tab2 = ttk.Frame(self.notebook)

        self.notebook.add(self.tab1, text="Tryb 1: Rozdzielone (Nagłówek + Folder)")
        self.notebook.add(self.tab2, text="Tryb 2: Zintegrowane (Jeden plik)")

        self.setup_tab1()
        self.setup_tab2()

        # Wspólne logi na dole
        self.log_text = tk.Text(root, height=8, width=60, state=tk.DISABLED, bg="#f0f0f0")
        self.log_text.pack(pady=10)

    def log(self, message):
        """Wypisuje tekst w okienku logów"""
        self.log_text.config(state=tk.NORMAL)
        self.log_text.insert(tk.END, message + "\n")
        self.log_text.see(tk.END)
        self.log_text.config(state=tk.DISABLED)
        self.root.update()

    # ==========================================
    # TRYB 1: ROZDZIELONE PLIKI (Poprzedni kod)
    # ==========================================
    def setup_tab1(self):
        self.header_path = None
        self.data_folder = None

        tk.Label(self.tab1, text="Wybierz plik nagłówka (z RAWI)", font=("Arial", 10, "bold")).pack(pady=(10, 5))
        self.lbl_h1 = tk.Label(self.tab1, text="Brak pliku", fg="gray")
        tk.Button(self.tab1, text="Wybierz nagłówek", command=self.t1_select_header, width=30).pack()
        self.lbl_h1.pack(pady=(0, 15))

        tk.Label(self.tab1, text="Wybierz folder z danymi (.raw)", font=("Arial", 10, "bold")).pack(pady=(0, 5))
        self.lbl_f1 = tk.Label(self.tab1, text="Brak folderu", fg="gray")
        tk.Button(self.tab1, text="Wybierz folder", command=self.t1_select_folder, width=30).pack()
        self.lbl_f1.pack(pady=(0, 15))

        self.btn_conv1 = tk.Button(self.tab1, text="Konwertuj (Tryb 1)", command=self.t1_convert, font=("Arial", 11, "bold"), bg="#4CAF50", fg="white", state=tk.DISABLED)
        self.btn_conv1.pack(pady=10, fill="x", padx=50)

    def t1_select_header(self):
        path = filedialog.askopenfilename(title="Wybierz nagłówek")
        if path:
            self.header_path = path
            self.lbl_h1.config(text=os.path.basename(path), fg="black")
            if self.data_folder: self.btn_conv1.config(state=tk.NORMAL)

    def t1_select_folder(self):
        path = filedialog.askdirectory(title="Wybierz folder")
        if path:
            self.data_folder = path
            self.lbl_f1.config(text=path, fg="black")
            if self.header_path: self.btn_conv1.config(state=tk.NORMAL)

    def t1_convert(self):
        try:
            self.log("--- TRYB 1 ---")
            with open(self.header_path, 'rb') as f: data = f.read()

            idx = data.find(b'\xFE\xFF')
            if idx == -1: raise ValueError("Brak struktury audio w nagłówku!")

            channels = int.from_bytes(data[idx+2:idx+4], 'little')
            sample_rate = int.from_bytes(data[idx+4:idx+8], 'little')
            bit_depth = int.from_bytes(data[idx+14:idx+16], 'little')

            end_pos = len(data) - 1
            while end_pos > 0 and data[end_pos] == 0: end_pos -= 1
            start_pos = end_pos
            while start_pos > 0 and 32 <= data[start_pos-1] <= 126: start_pos -= 1
            
            raw_name = data[start_pos:end_pos+1].decode('ascii', errors='ignore')
            self.log(f"Parametry: {sample_rate}Hz, {channels}kan, {bit_depth}bit")
            
            raw_path = os.path.join(self.data_folder, raw_name)
            if not os.path.exists(raw_path): raise FileNotFoundError(f"Nie znaleziono: {raw_name}")

            with open(raw_path, 'rb') as f: raw_data = f.read()
            self.export_audio(raw_data, sample_rate, bit_depth, channels, self.header_path)

        except Exception as e:
            self.log(f"BŁĄD: {e}")

    # ==========================================
    # TRYB 2: ZINTEGROWANY PLIK (Nowy format)
    # ==========================================
    def setup_tab2(self):
        self.single_file_path = None

        tk.Label(self.tab2, text="Wybierz ZINTEGROWANY plik audio", font=("Arial", 10, "bold")).pack(pady=(30, 5))
        self.lbl_s2 = tk.Label(self.tab2, text="Brak pliku", fg="gray")
        tk.Button(self.tab2, text="Wybierz plik", command=self.t2_select_file, width=30).pack()
        self.lbl_s2.pack(pady=(0, 30))

        self.btn_conv2 = tk.Button(self.tab2, text="Konwertuj (Tryb 2)", command=self.t2_convert, font=("Arial", 11, "bold"), bg="#2196F3", fg="white", state=tk.DISABLED)
        self.btn_conv2.pack(pady=10, fill="x", padx=50)

    def t2_select_file(self):
        path = filedialog.askopenfilename(title="Wybierz pojedynczy plik audio")
        if path:
            self.single_file_path = path
            self.lbl_s2.config(text=os.path.basename(path), fg="black")
            self.btn_conv2.config(state=tk.NORMAL)

    def t2_convert(self):
        try:
            self.log("--- TRYB 2 ---")
            with open(self.single_file_path, 'rb') as f: data = f.read()

            # Szukamy struktury
            idx = data.find(b'\xFE\xFF')
            if idx == -1: raise ValueError("W pliku nie znaleziono parametrów audio (brak 'FE FF')")

            channels = int.from_bytes(data[idx+2:idx+4], 'little')
            sample_rate = int.from_bytes(data[idx+4:idx+8], 'little')
            bit_depth = int.from_bytes(data[idx+14:idx+16], 'little')

            self.log(f"Parametry wtopione: {sample_rate}Hz, {channels}kan, {bit_depth}bit")

            # Próba odczytania wskaźnika (pointera) z bajtów 36-39
            offset = int.from_bytes(data[36:40], 'little')
            
            # Jeśli wskaźnik pokazuje absurdalną liczbę, używamy twardego 136 z naszej analizy
            if offset < idx or offset > len(data):
                self.log("Wskaźnik danych wygląda dziwnie. Zakładam offset = 136 bajtów.")
                offset = 136
            else:
                self.log(f"Początek danych audio od bajtu: {offset}")

            raw_data = data[offset:] # Ucinamy nagłówek, zostawiamy samo audio
            self.export_audio(raw_data, sample_rate, bit_depth, channels, self.single_file_path)

        except Exception as e:
            self.log(f"BŁĄD: {e}")

    # ==========================================
    # WSPÓLNA FUNKCJA ZAPISU DO MP3 / WAV
    # ==========================================
    def export_audio(self, raw_data, sample_rate, bit_depth, channels, source_path):
        self.log("Konwertowanie...")
        audio = AudioSegment(data=raw_data, sample_width=bit_depth // 8, frame_rate=sample_rate, channels=channels)
        
        base = os.path.splitext(source_path)[0]
        out_mp3 = base + ".mp3"
        out_wav = base + ".wav"

        try:
            audio.export(out_mp3, format="mp3")
            self.log("✅ GOTOWE! Zapisano MP3.")
        except Exception:
            self.log("Brak FFmpeg! Zapisano jako WAV.")
            audio.export(out_wav, format="wav")
            
        messagebox.showinfo("Sukces", "Eksport zakończony powodzeniem!")

if __name__ == "__main__":
    root = tk.Tk()
    app = GameAudioExtractorApp(root)
    root.mainloop()
