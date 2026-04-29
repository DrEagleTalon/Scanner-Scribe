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

# Make Directory relative to the scripts location instead of a hard coded location

BASE_DIR = Path(__file__).resolve().parent

# Fast testing model
MODEL_PATH = BASE_DIR / "models" / "vosk-model-small-en-us-0.15"

# Normal model
# MODEL_PATH = BASE_DIR / "models" / "vosk-model-en-us-0.22"

# Big model
# MODEL_PATH = BASE_DIR / "models" / "vosk-model-en-us-0.42-gigaspeech"

TRANSCRIPT_FOLDER = BASE_DIR / "transcripts"
AUDIO_FOLDER = BASE_DIR / "audio_recordings"

# Switch models here when needed to hard code the paths, remove comment hash on these paths and add them to the BASE_DIR paths above.

# Fast testing model:
# MODEL_PATH = r"C:\scanner-scribe\models\vosk-model-small-en-us-0.15"

# Big model:
# MODEL_PATH = r"C:\scanner-scribe\models\vosk-model-en-us-0.42-gigaspeech"

# TRANSCRIPT_FOLDER = r"C:\scanner-scribe\transcripts"
# AUDIO_FOLDER = r"C:\scanner-scribe\audio_recordings"

# For Stereo Mix / browser audio, 48000 is usually safer.
SAMPLE_RATE = 48000

# Use your actual input device.
# For your Stereo Mix, this was probably 32.
DEVICE_INDEX = 25

# Keep this 1 unless you know you need stereo.
CHANNELS = 1

# Set True if you want to save the exact incoming audio to .wav.
SAVE_WAV = True

# Set True if you want a raw-vs-clean comparison transcript.
SAVE_COMPARE = True

# Set True if you want scanner correction rules applied.
ENABLE_CORRECTIONS = True

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
# CLI PROMPT HELPERS
# --------------------------------------------------

def ask_text(prompt, default=None):
    if default is None:
        value = input(f"{prompt}: ").strip()
    else:
        value = input(f"{prompt} [{default}]: ").strip()

    if value == "":
        return default

    return value


def ask_yes_no(prompt, default=True):
    if default:
        hint = "Y/n"
    else:
        hint = "y/N"

    while True:
        value = input(f"{prompt} [{hint}]: ").strip().lower()

        if value == "":
            return default

        if value in ("y", "yes"):
            return True

        if value in ("n", "no"):
            return False

        print("Please enter y or n.")


def ask_int(prompt, default, minimum=None, maximum=None):
    while True:
        value = input(f"{prompt} [{default}]: ").strip()

        if value == "":
            return default

        try:
            number = int(value)
        except ValueError:
            print("Please enter a number.")
            continue

        if minimum is not None and number < minimum:
            print(f"Please enter a number >= {minimum}.")
            continue

        if maximum is not None and number > maximum:
            print(f"Please enter a number <= {maximum}.")
            continue

        return number


def get_input_devices():
    devices = sd.query_devices()
    input_devices = []

    for index, device in enumerate(devices):
        max_inputs = int(device.get("max_input_channels", 0))

        if max_inputs > 0:
            input_devices.append((index, device))

    return input_devices


def choose_audio_device(default_device_index):
    input_devices = get_input_devices()

    print("\nUsable input devices:\n")

    for index, device in input_devices:
        name = device.get("name", "Unknown")
        max_inputs = device.get("max_input_channels", 0)
        default_samplerate = int(device.get("default_samplerate", 0))

        marker = ""

        if index == default_device_index:
            marker = "  <-- current default"

        print(
            f"[{index}] {name} "
            f"({max_inputs} input channel(s), default {default_samplerate} Hz)"
            f"{marker}"
        )

    valid_indexes = [index for index, device in input_devices]

    if default_device_index not in valid_indexes:
        print(
            f"\nCurrent DEVICE_INDEX {default_device_index} is not a usable input device."
        )

        if input_devices:
            default_device_index = input_devices[0][0]
            print(f"Using first available input device as default: {default_device_index}")

    while True:
        selected = ask_int("Choose audio input device", default_device_index)

        if selected in valid_indexes:
            return selected

        print("That device is not a usable input device. Choose a device with input channels.")


def choose_channels(device_index, default_channels):
    device = sd.query_devices(device_index)
    max_inputs = int(device.get("max_input_channels", 1))

    if default_channels > max_inputs:
        default_channels = 1

    return ask_int(
        f"Channels to capture, usually 1 for Vosk",
        default_channels,
        minimum=1,
        maximum=max_inputs,
    )


def choose_model(default_model_path):
    models_dir = BASE_DIR / "models"

    print("\nAvailable Vosk models:\n")

    model_paths = []

    if models_dir.exists():
        for path in sorted(models_dir.iterdir()):
            if path.is_dir():
                model_paths.append(path)

    if not model_paths:
        print("No model folders found in models/.")
        print(f"Current default model path: {default_model_path}")
        typed_path = ask_text("Enter model path or press Enter to keep default", str(default_model_path))
        return Path(typed_path)

    for number, path in enumerate(model_paths, start=1):
        marker = ""

        if Path(default_model_path) == path:
            marker = "  <-- current default"

        print(f"[{number}] {path.name}{marker}")

    print("[0] Keep current default")

    while True:
        choice = ask_int("Choose model", 0, minimum=0, maximum=len(model_paths))

        if choice == 0:
            return Path(default_model_path)

        return model_paths[choice - 1]


def choose_folder(prompt, default_folder):
    selected = ask_text(prompt, str(default_folder))
    return Path(selected).expanduser()


def make_safe_session_name(user_input):
    if not user_input:
        return ""

    text = user_input.lower().strip()

    # Remove punctuation that should not split a word.
    text = text.replace("'", "")
    text = text.replace('"', "")
    text = text.replace("`", "")

    # Replace spaces, slashes, underscores, periods, and punctuation with hyphens.
    text = re.sub(r"[^a-z0-9]+", "-", text)

    # Remove words already represented in the filename.
    banned_words = {
        "scanner",
        "scribe",
        "transcribe",
        "transcriber",
        "transcript",
        "clean",
        "raw",
    }

    parts = [part for part in text.split("-") if part and part not in banned_words]

    safe_name = "-".join(parts)

    # Collapse repeated hyphens just in case.
    safe_name = re.sub(r"-+", "-", safe_name).strip("-")

    return safe_name


def make_output_paths(transcript_dir, audio_dir, session_name):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    safe_session_name = make_safe_session_name(session_name)

    if safe_session_name:
        suffix = f"_{safe_session_name}"
    else:
        suffix = ""

    clean_file = transcript_dir / f"scanner-transcribe_{timestamp}{suffix}.txt"
    compare_file = transcript_dir / f"scanner-transcribe-compare_{timestamp}{suffix}.txt"
    wav_output_file = audio_dir / f"scanner-audio_{timestamp}{suffix}.wav"

    return clean_file, compare_file, wav_output_file


# --------------------------------------------------
# COLLECT CLI SETTINGS
# --------------------------------------------------

print("\nScannerScribe CLI Setup")
print("-----------------------")
print("Press Enter to keep the default shown in brackets.\n")

MODEL_PATH = choose_model(MODEL_PATH)

DEVICE_INDEX = choose_audio_device(DEVICE_INDEX)

SAMPLE_RATE = ask_int("Sample rate", SAMPLE_RATE, minimum=8000, maximum=192000)

CHANNELS = choose_channels(DEVICE_INDEX, CHANNELS)

SAVE_WAV = ask_yes_no("Save WAV recording", SAVE_WAV)

SAVE_COMPARE = ask_yes_no("Save raw-vs-clean comparison transcript", SAVE_COMPARE)

ENABLE_CORRECTIONS = ask_yes_no("Enable scanner correction rules", ENABLE_CORRECTIONS)

TRANSCRIPT_FOLDER = choose_folder("Transcript save folder", TRANSCRIPT_FOLDER)

if SAVE_WAV:
    AUDIO_FOLDER = choose_folder("Audio recording save folder", AUDIO_FOLDER)

SESSION_NAME = ask_text("Optional session name for filenames", "")

# --------------------------------------------------
# SETUP FILES
# --------------------------------------------------

audio_queue = queue.Queue()

transcript_dir = Path(TRANSCRIPT_FOLDER)
transcript_dir.mkdir(parents=True, exist_ok=True)

audio_dir = Path(AUDIO_FOLDER)
audio_dir.mkdir(parents=True, exist_ok=True)

clean_transcript_file, compare_transcript_file, wav_file = make_output_paths(
    transcript_dir,
    audio_dir,
    SESSION_NAME,
)


# --------------------------------------------------
# HELPER FUNCTIONS
# --------------------------------------------------

def audio_callback(indata, frames, time_info, status):
    if status:
        print(status, file=sys.stderr)

    audio_queue.put(bytes(indata))


def clean_scanner_text(text):
    cleaned = text.lower().strip()

    if ENABLE_CORRECTIONS:
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

    if SAVE_COMPARE:
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
print(f"MODEL_PATH: {MODEL_PATH}")
print(f"DEVICE_INDEX: {DEVICE_INDEX}")
print(f"SAMPLE_RATE: {SAMPLE_RATE}")
print(f"CHANNELS: {CHANNELS}")
print(f"SAVE_WAV: {SAVE_WAV}")
print(f"SAVE_COMPARE: {SAVE_COMPARE}")
print(f"ENABLE_CORRECTIONS: {ENABLE_CORRECTIONS}")

print("\nTranscript files:")
print(f"Clean transcript:       {clean_transcript_file}")

if SAVE_COMPARE:
    print(f"Raw-vs-clean transcript:{compare_transcript_file}")

if SAVE_WAV:
    print(f"WAV recording:          {wav_file}")

print("\nPress Ctrl+C to stop.\n")

# --------------------------------------------------
# VALIDATE AUDIO DEVICE BEFORE LOADING MODEL
# --------------------------------------------------

device_info = sd.query_devices(DEVICE_INDEX)

if device_info["max_input_channels"] < 1:
    raise ValueError(
        f"DEVICE_INDEX {DEVICE_INDEX} is not an input device. "
        f"It has {device_info['max_input_channels']} input channels. "
        f"Choose a device with input channels."
    )

sd.check_input_settings(
    device=DEVICE_INDEX,
    samplerate=SAMPLE_RATE,
    channels=CHANNELS,
    dtype="int16",
)

print("Audio input device check passed.")


# --------------------------------------------------
# LOAD MODEL
# --------------------------------------------------

if not Path(MODEL_PATH).exists():
    raise FileNotFoundError(f"Model path not found: {MODEL_PATH}")

print("Loading Vosk model. This can take a while...")
model = Model(str(MODEL_PATH))
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

    if SAVE_COMPARE:
        print(f"Raw-vs-clean transcript: {compare_transcript_file}")

    if SAVE_WAV:
        print(f"WAV recording:           {wav_file}")