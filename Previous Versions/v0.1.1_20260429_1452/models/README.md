Download Vosk models separately and place them here.
Models are not included in this repository.

```text
ScannerScribe is a local scanner-audio transcription project. The current version is a CLI transcriber that listens to a selected Windows audio input, transcribes speech with Vosk, applies scanner-specific cleanup rules, and saves transcripts. The long-term goal is a GUI tool that can show raw and cleaned scanner text, detect keywords, and send local or email notifications.
```

## Suggested repo structure

Use something like this:

```text
scanner-scribe/
  README.md
  transcribe.py
  new_transcribe.py
  requirements.txt
  examples/
    scanner_phrases.txt
    scanner_corpus.txt
  docs/
    audio_devices.md
    correction_rules.md
    roadmap.md
  transcripts/
    .gitkeep
  audio_recordings/
    .gitkeep
  models/
    README.md
```

```text
Do **not** commit Vosk models to GitHub. They are huge.
Download Vosk models separately and place them here.
Models are not included in this repository.
```

````

For scanner audio, the most common setup is:

```text
Browser playing scanner audio
    ↓
Windows output device
    ↓
Stereo Mix or virtual audio cable
    ↓
ScannerScribe
```

## Installing

Install Python first.

Then install the Python requirements:

```powershell
pip install -r requirements.txt
```

Or manually:

```powershell
pip install vosk sounddevice
```

## Downloading a Vosk Model

Vosk models are not included in this repository.

Download a Vosk English model and place it somewhere like:

```text
C:\scanner-transcriber\models\
```

Example:

```text
C:\scanner-transcriber\models\vosk-model-small-en-us-0.15
C:\scanner-transcriber\models\vosk-model-en-us-0.22
C:\scanner-transcriber\models\vosk-model-en-us-0.42-gigaspeech
```

Inside the model folder, you should see folders such as:

```text
am
conf
graph
ivector
```

The `MODEL_PATH` setting must point directly to the folder that contains those files.

## Choosing a Model

The script allows switching models by changing `MODEL_PATH`.

Example:

```python
# Fast testing model
MODEL_PATH = r"C:\scanner-transcriber\models\vosk-model-small-en-us-0.15"

# Bigger, slower model
# MODEL_PATH = r"C:\scanner-transcriber\models\vosk-model-en-us-0.42-gigaspeech"
```

Only one `MODEL_PATH` should be active at a time.

Use the smaller model for testing. Use the larger model only after the audio setup is working.

## Audio Device Selection

When the script starts, it prints available audio devices.

A usable recording device will usually show something like:

```text
2 in, 0 out
```

or:

```text
1 in, 0 out
```

A speaker or output device will usually show:

```text
0 in, 2 out
```

The current script needs an input device. It cannot directly record from an output-only speaker device unless loopback or virtual audio routing is used.

Good candidates:

```text
Microphone
Stereo Mix
Virtual Audio Cable output
Loopback input
```

Bad candidates for the current input script:

```text
Speakers
Headphones
HDMI monitor output
Bluetooth speaker output
```

## Sample Rate

For Windows browser audio and Stereo Mix, `48000` is usually the safest sample rate.

Recommended setting:

```python
SAMPLE_RATE = 48000
```

Windows device properties should usually be set to:

```text
16-bit, 48000 Hz
```

Higher settings like 24-bit or 96000 Hz usually do not improve scanner transcription. Scanner audio is already compressed, noisy, and limited.

## Confidence Scores

Vosk can report confidence scores for recognized words.

The script enables this with:

```python
recognizer.SetWords(True)
```

That line belongs immediately after:

```python
recognizer = KaldiRecognizer(model, SAMPLE_RATE)
```

Example:

```python
recognizer = KaldiRecognizer(model, SAMPLE_RATE)
recognizer.SetWords(True)
print("Recognizer ready.")
```

The script then averages the confidence of the words in each completed transcription result.

Example output:

```text
[2026-04-29 08:52:14] [conf=0.82] wabash county units respond to a 10-50
```

Rough guide:

```text
0.85 - 1.00 = probably good
0.65 - 0.85 = usable but check it
0.40 - 0.65 = weak
below 0.40 = probably poor audio or guessing
```

Confidence is not proof. It is just a useful warning signal.

## Level 1 Corrections

Level 1 correction means:

```text
Vosk repeatedly hears phrase A wrong
You tell the script to replace it with phrase B
```

Example:

```python
(r"\bten fifty\b", "10-50"),
(r"\bwall bash\b", "Wabash"),
(r"\bin root\b", "en route"),
```

If Vosk writes:

```text
la grow
```

but you want:

```text
Lagro
```

add:

```python
(r"\bla grow\b", "Lagro"),
```

Then restart the script.

This is not full model training. It is post-processing. But for scanner audio, this is one of the fastest ways to improve readability.

## Level 2 Domain Corpus

A domain corpus is a plain text file of realistic scanner sentences.

Create:

```text
scanner_corpus.txt
```

Format it as one corrected scanner sentence per line.

Example:

```text
wabash county units respond to a ten fifty property damage accident near state road fifteen
grant county sheriff is en route to a domestic disturbance
city units be advised male subject may have a firearm
north manchester unit is on scene
medic requested for possible overdose
county units clear the scene
grant county dispatch to marion unit two
wabash city unit is out on a traffic stop
possible shots fired complaint near the residence
female subject advised the male subject left on foot
```

For the corpus, use the spoken version more than the display version.

Better for future language adaptation:

```text
ten fifty
ten thirty two
state road fifteen
```

Not always:

```text
10-50
10-32
SR-15
```

The speech model hears words. Display cleanup can happen later with correction rules.

So use:

```text
ten fifty property damage accident
```

in the corpus, then use correction rules to display:

```text
10-50 property damage accident
```

## Level 3 Language Model Adaptation

Language model adaptation is a future step.

It roughly means:

```text
1. Collect corrected scanner text
2. Normalize it into a corpus
3. Add local place names, agency names, street names, and scanner phrases
4. Update the model language data so those phrases become more likely
5. Possibly update the dictionary if words are missing
6. Rebuild the decoding graph
7. Test the adapted model against the same WAV samples
```

This is not the same as acoustic training.

Language model adaptation teaches the recognizer:

```text
These are the words and phrases likely to be said.
```

Acoustic model training teaches it:

```text
This is what those words sound like over bad scanner audio.
```

Language model adaptation should come first. Acoustic model training is much harder and should be revisited much later.

## Running the Script

Example:

```powershell
cd C:\scanner-transcriber
python transcribe.py
```

Or:

```powershell
py transcribe.py
```

Stop it with:

```text
Ctrl+C
```

The transcript will be saved to the configured transcript folder.

## Current Limitations

* Scanner audio is noisy and imperfect.
* Vosk may mishear radio codes, names, and street names.
* Multiple streams talking at once will reduce accuracy.
* The script currently requires manual settings changes in the Python file.
* The current version is CLI only.
* It does not yet send notifications.
* It does not yet have a GUI.

## Development Roadmap

### Phase 1: Stable CLI Transcriber

* Basic transcription
* Timestamps
* Confidence scores
* Scanner correction rules
* Clean transcript file

### Phase 2: Friendlier CLI

* Interactive startup menu
* Filter input devices
* Ask for sample rate
* Ask whether to save WAV
* Ask for session name
* Better filenames
* Optional raw-vs-clean transcript

### Phase 3: GUI

* Device selector
* Model selector
* Live transcript windows
* Settings panel
* Correction rule editor

### Phase 4: Alerts

* Keyword list
* Desktop notifications
* Sound alerts
* Email notifications

### Phase 5: Advanced Adaptation

* Domain corpus
* Language model adaptation
* Testing against saved WAV samples
* Possible acoustic model training much later

````

## CLI startup questions

The script should eventually ask questions like:

```text
1. Which audio input device?
2. Which model?
3. Which sample rate?
4. Save WAV recording? yes/no
5. Save raw-vs-clean comparison file? yes/no
6. Custom transcript folder or default?
7. Session name or default?
8. Enable correction rules? yes/no
9. Show confidence scores? yes/no
````


Example flow:

```text
ScannerScribe CLI

Usable input devices:
[1] External Microphone - WASAPI - 2 channels
[23] Desktop Microphone - WASAPI - 2 channels
[32] Stereo Mix - WDM-KS - 2 channels

Choose audio input [default: 32]:

Sample rate [default: 48000]:

Save WAV recording? [y/N]:

Save raw-vs-clean comparison transcript? [Y/n]:

Session name, optional [press Enter to skip]:

Starting transcription...
```

## Filename behavior

```text
scanner-transcribe_YYYYMMDD_HHMM.txt
```

With a session name:

```text
scanner-transcribe_YYYYMMDD_HHMM_wabash-police-sheriffs-traffic.txt
```

Local example:

```text
wabash police/sheriff's scanner_traffic
```

should become:

```text
wabash-police-sheriffs-traffic
```

Rules:

```text
lowercase everything
remove apostrophes and quotes
replace spaces, slashes, underscores, and most punctuation with hyphens
remove duplicate hyphens
remove words already in base filename: scanner, transcribe, transcript
strip hyphens from beginning and end
```

Later, that function would look like this:

```python
import re

def make_safe_session_name(user_input):
    text = user_input.lower().strip()

    # Remove apostrophes and quotes without adding hyphens.
    text = text.replace("'", "")
    text = text.replace('"', "")

    # Remove words already represented by the base filename.
    banned_words = {"scanner", "transcribe", "transcript"}

    words = re.split(r"[\s_/\\.-]+", text)
    words = [w for w in words if w and w not in banned_words]

    text = "-".join(words)

    # Replace any remaining unsafe characters with hyphens.
    text = re.sub(r"[^a-z0-9-]+", "-", text)

    # Collapse repeated hyphens.
    text = re.sub(r"-+", "-", text)

    return text.strip("-")
```

Then:

```python
def make_transcript_filename(session_name=None):
    stamp = datetime.now().strftime("%Y%m%d_%H%M")
    base = f"scanner-transcribe_{stamp}"

    if session_name:
        safe_name = make_safe_session_name(session_name)
        if safe_name:
            base = f"{base}_{safe_name}"

    return f"{base}.txt"
```

Example:

```python
make_safe_session_name("wabash police/sheriff's scanner_traffic")
```

returns:

```text
wabash-police-sheriffs-traffic
```

So the final file becomes:

```text
scanner-transcribe_20260429_0856_wabash-police-sheriffs-traffic.txt
```

## Why my confidence-code suggestion looked different

Your current code:

```python
words = result.get("result", [])
if words:
    avg_conf = sum(w.get("conf", 0) for w in words) / len(words)
else:
    avg_conf = 0

if text:
    write_line(f"[conf={avg_conf:.2f}] {text}")
```

What it does:

```text
1. Get the word list from Vosk.
2. If words exist, average their confidence values.
3. If no words exist, set confidence to 0.
4. Write the text with confidence formatted as a number.
```

That works.

The only weak part is this:

```python
avg_conf = 0
```

Because `0.00` means “confidence is terrible,” but sometimes the real issue is “there was no word-level confidence result.” Those are different.

My suggested version:

```python
words = result.get("result", [])

if words:
    avg_conf = sum(w.get("conf", 0) for w in words) / len(words)
    conf_text = f"conf={avg_conf:.2f}"
else:
    conf_text = "conf=unknown"

if text:
    write_line(f"[{conf_text}] {text}")
```

What changed:

```text
1. It still gets the word list.
2. It still averages confidence if words exist.
3. But if no words exist, it writes conf=unknown instead of conf=0.00.
4. It creates conf_text as a reusable display string.
```

That matters more once you start writing two logs:

```text
clean transcript
raw-vs-clean comparison transcript
```

Because now you can reuse:

```python
conf_text
```

in both places instead of formatting the confidence again and again.

So the difference is not about recognition. It does **not** make Vosk smarter. It just makes your output more honest and reusable.

## Which version should you use?

For a simple first version, your current code is fine.

I would only change this:

```python
else:
    avg_conf = 0
```

to the `conf_text = "conf=unknown"` pattern once you add raw-vs-clean transcript logging.

For now:

```text
Your version = fine for basic transcript
My version = better for future structured output
```

## How I would stage the repo

Keep this simple.

### Commit 1

```text
Initial CLI transcriber
```

Files:

```text
transcribe.py
requirements.txt
README.md
```

### Commit 2

```text
Add confidence scores
```

### Commit 3

```text
Add scanner correction rules
```

### Commit 4

```text
Add raw-vs-clean transcript logging
```

### Commit 5

```text
Add interactive startup prompts
```

### Commit 6

```text
Add optional WAV recording
```

This makes the project history clean and understandable. It also helps you learn because each change has a purpose.

Reply Given On: 2026/04/29 @ 2400
Conversation Name: ScannerScribe CLI Buildout
Conversation Categories: #Python #SpeechToText #GitHub #ScannerTranscription
Reply Category: #ProjectPlanning
Conversation ID: 20260429-ScannerScribe-cli
Reply ID Number: 14
