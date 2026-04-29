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