import json
import queue
import re
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
# SCANNER CORRECTION RULES
# --------------------------------------------------
# This is Level 1 "training": repeated mistake correction.
# Add to this list as you notice bad repeated transcriptions.

REPLACEMENTS = [
    # 10 codes
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
    (r"\bten ninety-five\b", "10-95"),

    # Common scanner phrases
    (r"\bshots fire\b", "shots fired"),
    (r"\bshot fired\b", "shots fired"),
    (r"\bin root\b", "en route"),
    (r"\bon seen\b", "on scene"),
    (r"\bclear to scene\b", "clear the scene"),

    # Local names / places
    (r"\bwall bash\b", "Wabash"),
    (r"\bwab ash\b", "Wabash"),
    (r"\bnorth man chester\b", "North Manchester"),
    (r"\bla fountain\b", "La Fontaine"),
    (r"\blafountain\b", "La Fontaine"),
    (r"\bgas city\b", "Gas City"),
    (r"\bjones burrow\b", "Jonesboro"),
    (r"\bjones borough\b", "Jonesboro"),

    # Agencies / units
    (r"\bgrant county sheriff's\b", "Grant County Sheriff's"),
    (r"\bwabash county sheriff's\b", "Wabash County Sheriff's"),
    (r"\bcounty unit\b", "county unit"),
    (r"\bcounty units\b", "county units"),
]


# --------------------------------------------------
# SETUP
# --------------------------------------------------

audio_queue = queue.Queue()

transcript_dir = Path(TRANSCRIPT_FOLDER)
transcript_dir.mkdir(parents=True, exist_ok=True)

date_stamp = datetime.now().strftime("%Y-%m-%d")
clean_transcript_file = transcript_dir / f"scanner-clean-{date_stamp}.txt"
compare_transcript_file = transcript_dir / f"scanner-raw-vs-clean-{date_stamp}.txt"


def audio_callback(indata, frames, time_info, status):
    if status:
        print(status, file=sys.stderr)

    audio_queue.put(bytes(indata))


def write_clean_line(text):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{timestamp}] {text}"

    print(line)

    with open(clean_transcript_file, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def write_compare_line(raw_text, clean_text, conf_text):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    with open(compare_transcript_file, "a", encoding="utf-8") as f:
        f.write(f"[{timestamp}] [{conf_text}]\n")
        f.write(f"RAW:   {raw_text}\n")
        f.write(f"CLEAN: {clean_text}\n")
        f.write("\n")


def clean_scanner_text(text):
    cleaned = text.lower().strip()

    for wrong_pattern, right_text in REPLACEMENTS:
        cleaned = re.sub(wrong_pattern, right_text, cleaned, flags=re.IGNORECASE)

    cleaned = re.sub(r"\s+", " ", cleaned).strip()

    return cleaned


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
                    clean_text = clean_scanner_text(text)
                    conf_text = f"conf={avg_conf:.2f}"

                    write_clean_line(f"[{conf_text}] {clean_text}")
                    write_compare_line(text, clean_text, conf_text)

except KeyboardInterrupt:
    print("\nStopped transcription.")

    final_result = json.loads(recognizer.FinalResult())
    final_text = final_result.get("text", "").strip()

    if final_text:
        clean_final_text = clean_scanner_text(final_text)
        conf_text = "conf=final"

        write_clean_line(f"[{conf_text}] {clean_final_text}")
        write_compare_line(final_text, clean_final_text, conf_text)

    print(f"\nSaved transcript to:\n{transcript_file}")