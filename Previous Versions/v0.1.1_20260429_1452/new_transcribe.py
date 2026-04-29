import json
import queue
import re
import sys
import wave
from datetime import datetime
from pathlib import Path

import sounddevice as sd
from vosk import Model, KaldiRecognizer


# --------------------------------------------------
# SETTINGS
# --------------------------------------------------

# Switch models here when needed.
# Fast testing model:
MODEL_PATH = r"C:\scanner-transcriber\models\vosk-model-small-en-us-0.15"

# Big model:
# MODEL_PATH = r"C:\scanner-transcriber\models\vosk-model-en-us-0.42-gigaspeech"

TRANSCRIPT_FOLDER = r"C:\scanner-transcriber\transcripts"
AUDIO_FOLDER = r"C:\scanner-transcriber\audio_recordings"

# For Stereo Mix / browser audio, 48000 is usually safer.
SAMPLE_RATE = 48000

# Use your actual input device.
# For your Stereo Mix, this was probably 32.
DEVICE_INDEX = 32

# Keep this 1 unless you know you need stereo.
CHANNELS = 1

# Set True if you want to save the exact incoming audio to .wav.
SAVE_WAV = True


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
# SETUP FILES
# --------------------------------------------------

audio_queue = queue.Queue()

transcript_dir = Path(TRANSCRIPT_FOLDER)
transcript_dir.mkdir(parents=True, exist_ok=True)

audio_dir = Path(AUDIO_FOLDER)
audio_dir.mkdir(parents=True, exist_ok=True)

date_stamp = datetime.now().strftime("%Y-%m-%d")
time_stamp = datetime.now().strftime("%H%M%S")

clean_transcript_file = transcript_dir / f"scanner-clean-{date_stamp}.txt"
compare_transcript_file = transcript_dir / f"scanner-raw-vs-clean-{date_stamp}.txt"
wav_file = audio_dir / f"scanner-audio-{date_stamp}-{time_stamp}.wav"


# --------------------------------------------------
# HELPER FUNCTIONS
# --------------------------------------------------

def audio_callback(indata, frames, time_info, status):
    if status:
        print(status, file=sys.stderr)

    audio_queue.put(bytes(indata))


def clean_scanner_text(text):
    cleaned = text.lower().strip()

    for wrong_pattern, right_text in REPLACEMENTS:
        cleaned = re.sub(wrong_pattern, right_text, cleaned, flags=re.IGNORECASE)

    # Clean up extra spaces.
    cleaned = re.sub(r"\s+", " ", cleaned).strip()

    return cleaned


def get_average_confidence(result):
    words = result.get("result", [])

    if not words:
        return None

    confidence_values = []

    for word in words:
        if "conf" in word:
            confidence_values.append(word["conf"])

    if not confidence_values:
        return None

    return sum(confidence_values) / len(confidence_values)


def write_transcripts(raw_text, clean_text, confidence):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if confidence is None:
        conf_text = "conf=unknown"
    else:
        conf_text = f"conf={confidence:.2f}"

    clean_line = f"[{timestamp}] [{conf_text}] {clean_text}"

    # This is what you see in the CLI.
    print(clean_line)

    # Clean transcript file.
    with open(clean_transcript_file, "a", encoding="utf-8") as f:
        f.write(clean_line + "\n")

    # Raw-vs-clean comparison file.
    with open(compare_transcript_file, "a", encoding="utf-8") as f:
        f.write(f"[{timestamp}] [{conf_text}]\n")
        f.write(f"RAW:   {raw_text}\n")
        f.write(f"CLEAN: {clean_text}\n")
        f.write("\n")


def handle_result(result_json):
    result = json.loads(result_json)

    raw_text = result.get("text", "").strip()

    if not raw_text:
        return

    confidence = get_average_confidence(result)
    clean_text = clean_scanner_text(raw_text)

    write_transcripts(raw_text, clean_text, confidence)


# --------------------------------------------------
# SHOW AUDIO DEVICES
# --------------------------------------------------

print("\nAvailable audio devices:\n")
print(sd.query_devices())

print("\nCurrent settings:")
print(f"DEVICE_INDEX: {DEVICE_INDEX}")
print(f"SAMPLE_RATE: {SAMPLE_RATE}")
print(f"CHANNELS: {CHANNELS}")
print(f"SAVE_WAV: {SAVE_WAV}")

print("\nTranscript files:")
print(f"Clean transcript:       {clean_transcript_file}")
print(f"Raw-vs-clean transcript:{compare_transcript_file}")

if SAVE_WAV:
    print(f"WAV recording:          {wav_file}")

print("\nPress Ctrl+C to stop.\n")


# --------------------------------------------------
# LOAD MODEL
# --------------------------------------------------

if not Path(MODEL_PATH).exists():
    raise FileNotFoundError(f"Model path not found: {MODEL_PATH}")

print("Loading Vosk model. This can take a while...")
model = Model(MODEL_PATH)
print("Model loaded.")

recognizer = KaldiRecognizer(model, SAMPLE_RATE)

# This is what enables word-level confidence.
recognizer.SetWords(True)

print("Recognizer ready.")


# --------------------------------------------------
# START TRANSCRIBING
# --------------------------------------------------

wav_writer = None

try:
    if SAVE_WAV:
        wav_writer = wave.open(str(wav_file), "wb")
        wav_writer.setnchannels(CHANNELS)
        wav_writer.setsampwidth(2)  # int16 = 2 bytes
        wav_writer.setframerate(SAMPLE_RATE)

    with sd.RawInputStream(
        samplerate=SAMPLE_RATE,
        blocksize=8000,
        device=DEVICE_INDEX,
        dtype="int16",
        channels=CHANNELS,
        callback=audio_callback,
    ):
        while True:
            data = audio_queue.get()

            if SAVE_WAV and wav_writer is not None:
                wav_writer.writeframes(data)

            if recognizer.AcceptWaveform(data):
                handle_result(recognizer.Result())

except KeyboardInterrupt:
    print("\nStopped transcription.")

    final_result = recognizer.FinalResult()
    handle_result(final_result)

finally:
    if wav_writer is not None:
        wav_writer.close()

    print("\nSaved files:")
    print(f"Clean transcript:        {clean_transcript_file}")
    print(f"Raw-vs-clean transcript: {compare_transcript_file}")

    if SAVE_WAV:
        print(f"WAV recording:           {wav_file}")