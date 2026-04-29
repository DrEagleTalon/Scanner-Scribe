import json
import queue
import sys
from datetime import datetime
from pathlib import Path

import sounddevice as sd
from vosk import Model, KaldiRecognizer


# --------------------------------------------------
# SETTINGS
# --------------------------------------------------

# Fast testing model
# MODEL_PATH = r"C:\scanner-transcriber\vosk-model-small-en-us-0.15"
# Normal Sized model
# MODEL_PATH = r"C:\scanner-transcriber\vosk-model-en-us-0.22"
# Bigger, slower model
MODEL_PATH = r"C:\scanner-transcriber\vosk-model-en-us-0.42-gigaspeech"

TRANSCRIPT_FOLDER = r"C:\scanner-transcriber\transcripts"

SAMPLE_RATE = 48000

# Leave as None first.
# The script will print available audio devices.
# After you find the right one, set DEVICE_INDEX to that number.
DEVICE_INDEX = 25


# --------------------------------------------------
# SETUP
# --------------------------------------------------

audio_queue = queue.Queue()

transcript_dir = Path(TRANSCRIPT_FOLDER)
transcript_dir.mkdir(parents=True, exist_ok=True)

date_stamp = datetime.now().strftime("%Y-%m-%d")
transcript_file = transcript_dir / f"scanner-transcript-{date_stamp}.txt"


def audio_callback(indata, frames, time_info, status):
    if status:
        print(status, file=sys.stderr)

    audio_queue.put(bytes(indata))


def write_line(text):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{timestamp}] {text}"

    print(line)

    with open(transcript_file, "a", encoding="utf-8") as f:
        f.write(line + "\n")


# --------------------------------------------------
# SHOW AUDIO DEVICES
# --------------------------------------------------

print("\nAvailable audio devices:\n")
print(sd.query_devices())
print("\nCurrent DEVICE_INDEX:", DEVICE_INDEX)
print("\nTranscript file:")
print(transcript_file)
print("\nPress Ctrl+C to stop.\n")


# --------------------------------------------------
# LOAD MODEL
# --------------------------------------------------

if not Path(MODEL_PATH).exists():
    raise FileNotFoundError(f"Model path not found: {MODEL_PATH}")

print("Loading Vosk model. This may take a while for the large model...")
model = Model(MODEL_PATH)
print("Model loaded.")

recognizer = KaldiRecognizer(model, SAMPLE_RATE)
recognizer.SetWords(True)
print("Recognizer ready.")


# --------------------------------------------------
# START TRANSCRIBING
# --------------------------------------------------

try:
    with sd.RawInputStream(
        samplerate=SAMPLE_RATE,
        blocksize=8000,
        device=DEVICE_INDEX,
        dtype="int16",
        channels=1,
        callback=audio_callback,
    ):
        while True:
            data = audio_queue.get()

            if recognizer.AcceptWaveform(data):
                result = json.loads(recognizer.Result())
                text = result.get("text", "").strip()

                words = result.get("result", [])
                if words:
                    avg_conf = sum(w.get("conf", 0) for w in words) / len(words)
                else:
                    avg_conf = 0

                if text:
                    write_line(f"[conf={avg_conf:.2f}] {text}")

except KeyboardInterrupt:
    print("\nStopped transcription.")

    final_result = json.loads(recognizer.FinalResult())
    final_text = final_result.get("text", "").strip()

    if final_text:
        write_line(final_text)

    print(f"\nSaved transcript to:\n{transcript_file}")