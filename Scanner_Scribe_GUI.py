import json
import queue
import re
import threading
import wave
from datetime import datetime
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from tkinter.scrolledtext import ScrolledText

import sounddevice as sd
from vosk import KaldiRecognizer, Model

BASE_DIR = Path(__file__).resolve().parent
DEFAULT_MODEL_PATH = BASE_DIR / "models" / "vosk-model-small-en-us-0.15"
DEFAULT_TRANSCRIPT_FOLDER = BASE_DIR / "transcripts"
DEFAULT_AUDIO_FOLDER = BASE_DIR / "audio_recordings"

REPLACEMENTS = [
    (r"\bten four\b", "10-4"),
    (r"\bten fore\b", "10-4"),
    (r"\bten for\b", "10-4"),
    (r"\bten eight\b", "10-8"),
    (r"\bten ate\b", "10-8"),
    (r"\bten nine\b", "10-9"),
    (r"\bten thirty two\b", "10-32"),
    (r"\bten thirty too\b", "10-32"),
    (r"\bten thirty to\b", "10-32"),
    (r"\bten fifty\b", "10-50"),
    (r"\bten fifteen\b", "10-50"),
    (r"\bten seventy six\b", "10-76"),
    (r"\bten seven six\b", "10-76"),
    (r"\bten ninety five\b", "10-95"),
    (r"\bshots fire\b", "shots fired"),
    (r"\bshot fired\b", "shots fired"),
    (r"\bin root\b", "en route"),
    (r"\bon seen\b", "on scene"),
    (r"\bclear to scene\b", "clear the scene"),
    (r"\bwall bash\b", "Wabash"),
    (r"\bwab ash\b", "Wabash"),
    (r"\bnorth man chester\b", "North Manchester"),
    (r"\bla fountain\b", "La Fontaine"),
    (r"\blafountain\b", "La Fontaine"),
    (r"\bgas city\b", "Gas City"),
    (r"\bjones burrow\b", "Jonesboro"),
    (r"\bjones borough\b", "Jonesboro"),
]


class ScannerScribeGUI:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("ScannerScribe")

        self.stop_event = threading.Event()
        self.gui_queue = queue.Queue()
        self.audio_queue = queue.Queue()
        self.worker_thread = None
        self.device_map = {}

        self.build_form()
        self.build_output_windows()
        self.poll_gui_queue()

    def build_form(self):
        frame = ttk.LabelFrame(self.root, text="ScannerScribe Settings")
        frame.pack(fill="x", padx=10, pady=10)

        self.model_var = tk.StringVar(value=str(DEFAULT_MODEL_PATH))
        self.transcript_var = tk.StringVar(value=str(DEFAULT_TRANSCRIPT_FOLDER))
        self.audio_folder_var = tk.StringVar(value=str(DEFAULT_AUDIO_FOLDER))
        self.sample_rate_var = tk.StringVar(value="48000")
        self.channels_var = tk.StringVar(value="1")
        self.session_name_var = tk.StringVar()

        self.save_wav_var = tk.BooleanVar(value=True)
        self.save_compare_var = tk.BooleanVar(value=True)
        self.enable_corrections_var = tk.BooleanVar(value=True)

        ttk.Label(frame, text="Model Path").grid(row=0, column=0, sticky="w")
        ttk.Entry(frame, textvariable=self.model_var, width=70).grid(row=0, column=1, sticky="ew")
        ttk.Button(frame, text="Browse", command=self.browse_model).grid(row=0, column=2)

        ttk.Label(frame, text="Audio Input").grid(row=1, column=0, sticky="w")
        self.device_var = tk.StringVar()
        self.device_combo = ttk.Combobox(frame, textvariable=self.device_var, width=70, state="readonly")
        self.device_combo.grid(row=1, column=1, sticky="ew")
        ttk.Button(frame, text="Refresh", command=self.load_audio_devices).grid(row=1, column=2)

        ttk.Label(frame, text="Sample Rate").grid(row=2, column=0, sticky="w")
        ttk.Entry(frame, textvariable=self.sample_rate_var, width=15).grid(row=2, column=1, sticky="w")

        ttk.Label(frame, text="Channels").grid(row=3, column=0, sticky="w")
        ttk.Entry(frame, textvariable=self.channels_var, width=15).grid(row=3, column=1, sticky="w")

        ttk.Label(frame, text="Session Name").grid(row=4, column=0, sticky="w")
        ttk.Entry(frame, textvariable=self.session_name_var, width=40).grid(row=4, column=1, sticky="w")

        ttk.Label(frame, text="Transcript Folder").grid(row=5, column=0, sticky="w")
        ttk.Entry(frame, textvariable=self.transcript_var, width=70).grid(row=5, column=1, sticky="ew")
        ttk.Button(frame, text="Browse", command=self.browse_transcripts).grid(row=5, column=2)

        ttk.Label(frame, text="Audio Folder").grid(row=6, column=0, sticky="w")
        ttk.Entry(frame, textvariable=self.audio_folder_var, width=70).grid(row=6, column=1, sticky="ew")
        ttk.Button(frame, text="Browse", command=self.browse_audio).grid(row=6, column=2)

        ttk.Checkbutton(frame, text="Save WAV recording", variable=self.save_wav_var).grid(row=7, column=1, sticky="w")
        ttk.Checkbutton(frame, text="Save raw-vs-clean compare file", variable=self.save_compare_var).grid(row=8, column=1, sticky="w")
        ttk.Checkbutton(frame, text="Enable scanner correction rules", variable=self.enable_corrections_var).grid(row=9, column=1, sticky="w")

        button_frame = ttk.Frame(frame)
        button_frame.grid(row=10, column=1, sticky="w", pady=10)
        self.start_button = ttk.Button(button_frame, text="Start", command=self.start_transcription)
        self.start_button.pack(side="left", padx=5)
        self.stop_button = ttk.Button(button_frame, text="Stop", command=self.stop_transcription, state="disabled")
        self.stop_button.pack(side="left", padx=5)

        frame.columnconfigure(1, weight=1)
        self.load_audio_devices()

    def build_output_windows(self):
        output_frame = ttk.Frame(self.root)
        output_frame.pack(fill="both", expand=True, padx=10, pady=10)

        clean_frame = ttk.LabelFrame(output_frame, text="Clean Transcript")
        clean_frame.pack(side="left", fill="both", expand=True, padx=(0, 5))
        compare_frame = ttk.LabelFrame(output_frame, text="Raw vs Clean")
        compare_frame.pack(side="left", fill="both", expand=True, padx=(5, 0))

        self.clean_output = ScrolledText(clean_frame, wrap="word", height=25)
        self.clean_output.pack(fill="both", expand=True)
        self.compare_output = ScrolledText(compare_frame, wrap="word", height=25)
        self.compare_output.pack(fill="both", expand=True)

    def load_audio_devices(self):
        self.device_map = {}
        labels = []
        for index, device in enumerate(sd.query_devices()):
            max_inputs = int(device.get("max_input_channels", 0))
            if max_inputs > 0:
                name = device.get("name", "Unknown")
                default_rate = int(device.get("default_samplerate", 0))
                label = f"[{index}] {name} ({max_inputs} in, default {default_rate} Hz)"
                labels.append(label)
                self.device_map[label] = index
        self.device_combo["values"] = labels
        if labels:
            self.device_var.set(next((x for x in labels if "stereo mix" in x.lower()), labels[0]))

    def poll_gui_queue(self):
        try:
            while True:
                target, text = self.gui_queue.get_nowait()
                if target == "clean":
                    self.clean_output.insert("end", text + "\n")
                    self.clean_output.see("end")
                elif target == "compare":
                    self.compare_output.insert("end", text + "\n\n")
                    self.compare_output.see("end")
                elif target == "status":
                    self.clean_output.insert("end", f"[STATUS] {text}\n")
                    self.clean_output.see("end")
                elif target == "error":
                    messagebox.showerror("ScannerScribe Error", text)
                elif target == "done":
                    self.start_button.config(state="normal")
                    self.stop_button.config(state="disabled")
        except queue.Empty:
            pass
        self.root.after(100, self.poll_gui_queue)

    def start_transcription(self):
        if self.worker_thread and self.worker_thread.is_alive():
            return
        self.stop_event.clear()
        self.start_button.config(state="disabled")
        self.stop_button.config(state="normal")
        self.worker_thread = threading.Thread(target=self.transcription_worker, daemon=True)
        self.worker_thread.start()

    def stop_transcription(self):
        self.stop_event.set()
        self.gui_queue.put(("status", "Stopping transcription..."))

    def browse_model(self):
        folder = filedialog.askdirectory(title="Select Vosk model folder")
        if folder:
            self.model_var.set(folder)

    def browse_transcripts(self):
        folder = filedialog.askdirectory(title="Select transcript folder")
        if folder:
            self.transcript_var.set(folder)

    def browse_audio(self):
        folder = filedialog.askdirectory(title="Select audio recording folder")
        if folder:
            self.audio_folder_var.set(folder)

    def transcription_worker(self):
        wav_file = None
        clean_fh = None
        compare_fh = None
        try:
            model_path = Path(self.model_var.get().strip())
            transcript_folder = Path(self.transcript_var.get().strip())
            audio_folder = Path(self.audio_folder_var.get().strip())
            sample_rate = int(self.sample_rate_var.get().strip())
            channels = int(self.channels_var.get().strip())
            session_name = self.session_name_var.get().strip() or datetime.now().strftime("%Y%m%d_%H%M%S")

            device_label = self.device_var.get().strip()
            if device_label not in self.device_map:
                raise ValueError("Choose a valid audio input device.")
            device_index = self.device_map[device_label]

            if not model_path.exists():
                raise FileNotFoundError(f"Model folder not found: {model_path}")

            transcript_folder.mkdir(parents=True, exist_ok=True)
            audio_folder.mkdir(parents=True, exist_ok=True)

            clean_path = transcript_folder / f"{session_name}_clean.txt"
            compare_path = transcript_folder / f"{session_name}_compare.txt"
            wav_path = audio_folder / f"{session_name}.wav"

            clean_fh = clean_path.open("w", encoding="utf-8")
            if self.save_compare_var.get():
                compare_fh = compare_path.open("w", encoding="utf-8")

            if self.save_wav_var.get():
                wav_file = wave.open(str(wav_path), "wb")
                wav_file.setnchannels(channels)
                wav_file.setsampwidth(2)
                wav_file.setframerate(sample_rate)

            self.gui_queue.put(("status", "Loading Vosk model..."))
            model = Model(str(model_path))
            recognizer = KaldiRecognizer(model, sample_rate)

            def audio_callback(indata, frames, time_info, status):
                if status:
                    self.gui_queue.put(("status", f"Audio status: {status}"))
                chunk = bytes(indata)
                self.audio_queue.put(chunk)
                if wav_file is not None:
                    wav_file.writeframes(chunk)

            with sd.RawInputStream(
                samplerate=sample_rate,
                blocksize=8000,
                device=device_index,
                dtype="int16",
                channels=channels,
                callback=audio_callback,
            ):
                self.gui_queue.put(("status", "Transcription started."))
                while not self.stop_event.is_set():
                    try:
                        data = self.audio_queue.get(timeout=0.2)
                    except queue.Empty:
                        continue

                    if not recognizer.AcceptWaveform(data):
                        continue

                    result = json.loads(recognizer.Result())
                    raw_text = result.get("text", "").strip()
                    if not raw_text:
                        continue

                    clean_text = raw_text
                    if self.enable_corrections_var.get():
                        for pattern, replacement in REPLACEMENTS:
                            clean_text = re.sub(pattern, replacement, clean_text, flags=re.IGNORECASE)

                    clean_fh.write(clean_text + "\n")
                    clean_fh.flush()
                    self.gui_queue.put(("clean", clean_text))

                    if compare_fh is not None:
                        compare_block = f"RAW: {raw_text}\nCLEAN: {clean_text}"
                        compare_fh.write(compare_block + "\n\n")
                        compare_fh.flush()
                        self.gui_queue.put(("compare", compare_block))

                final_result = json.loads(recognizer.FinalResult())
                final_raw = final_result.get("text", "").strip()
                if final_raw:
                    final_clean = final_raw
                    if self.enable_corrections_var.get():
                        for pattern, replacement in REPLACEMENTS:
                            final_clean = re.sub(pattern, replacement, final_clean, flags=re.IGNORECASE)
                    clean_fh.write(final_clean + "\n")
                    self.gui_queue.put(("clean", final_clean))

            self.gui_queue.put(("status", f"Saved clean transcript: {clean_path}"))
            if compare_fh is not None:
                self.gui_queue.put(("status", f"Saved compare transcript: {compare_path}"))
            if wav_file is not None:
                self.gui_queue.put(("status", f"Saved WAV file: {wav_path}"))

        except Exception as exc:
            self.gui_queue.put(("error", str(exc)))
        finally:
            if clean_fh is not None:
                clean_fh.close()
            if compare_fh is not None:
                compare_fh.close()
            if wav_file is not None:
                wav_file.close()
            self.stop_event.set()
            self.gui_queue.put(("done", ""))


if __name__ == "__main__":
    root = tk.Tk()
    root.geometry("1300x780")
    app = ScannerScribeGUI(root)
    root.mainloop()
