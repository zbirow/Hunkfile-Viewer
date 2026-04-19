import os
import tkinter as tk
from tkinter import filedialog, messagebox
from pydub import AudioSegment

class RawiConverterApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Konwerter RAWI do MP3 (Automatyczne szukanie)")
        self.root.geometry("520x480")
        self.root.configure(padx=20, pady=20)

        self.header_path = None
        self.data_folder = None

        # --- SEKCJA 1: NAGŁÓWEK ---
        self.label_h = tk.Label(root, text="Krok 1: Wybierz plik nagłówka (ten z RAWI)", font=("Arial", 10, "bold"))
        self.label_h.pack(pady=(0, 5))

        self.btn_header = tk.Button(root, text="Wybierz plik nagłówka", command=self.select_header, width=30)
        self.btn_header.pack()

        self.lbl_header_file = tk.Label(root, text="Brak wybranego pliku", fg="gray", font=("Arial", 8))
        self.lbl_header_file.pack(pady=(0, 15))

        # --- SEKCJA 2: FOLDER Z DANYMI ---
        self.label_r = tk.Label(root, text="Krok 2: Wybierz FOLDER, w którym są pliki danych", font=("Arial", 10, "bold"))
        self.label_r.pack(pady=(0, 5))

        self.btn_folder = tk.Button(root, text="Wybierz folder", command=self.select_folder, width=30)
        self.btn_folder.pack()

        self.lbl_folder_path = tk.Label(root, text="Brak wybranego folderu", fg="gray", font=("Arial", 8), wraplength=450)
        self.lbl_folder_path.pack(pady=(0, 15))

        # --- SEKCJA LOGÓW I KONWERSJI ---
        self.log_text = tk.Text(root, height=8, width=58, state=tk.DISABLED, bg="#f0f0f0")
        self.log_text.pack(pady=5)

        self.btn_convert = tk.Button(root, text="Konwertuj", command=self.convert_file, font=("Arial", 11, "bold"), bg="#4CAF50", fg="white", width=30, state=tk.DISABLED)
        self.btn_convert.pack(pady=10)

    def log(self, message):
        """Wypisuje tekst w okienku logów"""
        self.log_text.config(state=tk.NORMAL)
        self.log_text.insert(tk.END, message + "\n")
        self.log_text.see(tk.END)
        self.log_text.config(state=tk.DISABLED)
        self.root.update()

    def check_ready(self):
        """Odblokowuje przycisk konwersji, jeśli wybrano plik i folder"""
        if self.header_path and self.data_folder:
            self.btn_convert.config(state=tk.NORMAL)

    def select_header(self):
        filepath = filedialog.askopenfilename(title="Wybierz plik nagłówkowy", filetypes=[("Wszystkie pliki", "*.*")])
        if filepath:
            self.header_path = filepath
            self.lbl_header_file.config(text=os.path.basename(filepath), fg="black")
            self.log("Załadowano plik nagłówka.")
            self.check_ready()

    def select_folder(self):
        folderpath = filedialog.askdirectory(title="Wybierz folder z danymi")
        if folderpath:
            self.data_folder = folderpath
            self.lbl_folder_path.config(text=folderpath, fg="black")
            self.log("Załadowano folder na dane.")
            self.check_ready()

    def parse_header(self, filepath):
        """Wyciąga parametry oraz NAZWĘ PLIKU Z DANYMI z nagłówka"""
        with open(filepath, 'rb') as f:
            data = f.read()

        if data.find(b'RAWI') == -1:
            raise ValueError("W pliku nagłówka nie znaleziono ciągu 'RAWI'.")

        idx = data.find(b'\xFE\xFF')
        if idx == -1:
            raise ValueError("W nagłówku brakuje struktury formatu (FE FF).")

        channels = int.from_bytes(data[idx+2:idx+4], 'little')
        sample_rate = int.from_bytes(data[idx+4:idx+8], 'little')
        bit_depth = int.from_bytes(data[idx+14:idx+16], 'little')

        # Wyciąganie nazwy pliku z końca nagłówka
        # Czytamy plik od końca pomijając puste bajty (0x00)
        end_pos = len(data) - 1
        while end_pos > 0 and data[end_pos] == 0:
            end_pos -= 1
        
        # Cofamy się, dopóki znaki są literami/cyframi (kod ASCII 32 - 126)
        start_pos = end_pos
        while start_pos > 0 and 32 <= data[start_pos-1] <= 126:
            start_pos -= 1
            
        raw_filename = data[start_pos:end_pos+1].decode('ascii', errors='ignore')

        self.log(f"Odczytano parametry: {sample_rate}Hz, {channels} kanał(y), {bit_depth}-bit")
        self.log(f"Zidentyfikowano plik danych: {raw_filename}")
        
        return channels, sample_rate, bit_depth, raw_filename

    def convert_file(self):
        try:
            self.btn_convert.config(state=tk.DISABLED)
            
            # 1. Odczytujemy parametry z pliku nagłówka
            self.log("Analizowanie nagłówka...")
            channels, sample_rate, bit_depth, raw_filename = self.parse_header(self.header_path)
            
            # 2. Szukamy wyciągniętego pliku w podanym folderze
            target_raw_path = os.path.join(self.data_folder, raw_filename)
            
            if not os.path.exists(target_raw_path):
                raise FileNotFoundError(f"Nie znaleziono pliku '{raw_filename}' w wybranym folderze!\nCzy na pewno to właściwy folder?")

            # 3. Odczytujemy twarde dane
            self.log("Wczytywanie surowych danych (RAW)...")
            with open(target_raw_path, 'rb') as f:
                raw_data = f.read()

            self.log("Przetwarzanie audio...")
            
            # 4. Złożenie tego w całość
            audio = AudioSegment(
                data=raw_data,
                sample_width=bit_depth // 8,
                frame_rate=sample_rate,
                channels=channels
            )

            # Plik wynikowy zapiszemy w tym samym miejscu, co oryginalny plik nagłówka
            directory = os.path.dirname(self.header_path)
            # Nazwa pliku wynikowego = nazwa nagłówka (ale z innym rozszerzeniem)
            base_name = os.path.splitext(os.path.basename(self.header_path))[0]
            
            output_mp3 = os.path.join(directory, base_name + ".mp3")
            output_wav = os.path.join(directory, base_name + ".wav")
            
            # 5. Próba zapisu
            try:
                self.log(f"Zapisywanie do MP3...")
                audio.export(output_mp3, format="mp3")
                self.log("✅ GOTOWE! Zapisano MP3.")
                messagebox.showinfo("Sukces", f"Zapisano plik:\n{output_mp3}")
                
            except Exception as mp3_error:
                # Jeśli wywali błąd (np. brak FFmpeg), zapisujemy jako WAV
                self.log("Brak programu FFmpeg do kompresji MP3!")
                self.log("Ratuję plik... Zapisuję jako .WAV...")
                audio.export(output_wav, format="wav")
                self.log("✅ GOTOWE! Zapisano WAV.")
                messagebox.showwarning("Sukces (Zapisano WAV)", f"Zapisano jako plik WAV, ponieważ brakowało FFmpeg.\n\n{output_wav}")

        except Exception as e:
            self.log(f"❌ Błąd: {str(e)}")
            messagebox.showerror("Błąd", str(e))
        finally:
            self.btn_convert.config(state=tk.NORMAL)

if __name__ == "__main__":
    root = tk.Tk()
    app = RawiConverterApp(root)
    root.mainloop()
