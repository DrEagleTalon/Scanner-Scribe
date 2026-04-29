Download Vosk models separately and place them here.
Models are not included in this repository.

# DispatchScribe

DispatchScribe is a local scanner-audio transcription project built with Python and Vosk.

The current version is a command-line transcriber that listens to a selected Windows audio input, transcribes scanner or dispatch audio, adds confidence scores, applies scanner-specific cleanup rules, and saves the result to a text file.

The long-term goal is to build this into a user-friendly scanner monitoring tool with:

- a GUI
- raw and cleaned transcript windows
- selectable audio input
- configurable scanner correction rules
- keyword alerts
- desktop notifications
- optional email notifications
- optional WAV/audio logging for review

This project is being built in stages. The current focus is a stable CLI transcriber.

## Important Legal and Use Notice

This tool is intended for lawful monitoring, accessibility, logging, research, and personal awareness.

Do not use this tool to assist in committing crimes, avoiding law enforcement, interfering with emergency services, or violating the terms of any audio provider.

If using Broadcastify or another streaming service, review their terms of service before automating access, recording, or redistribution.

## Current Features

- Local speech-to-text transcription using Vosk
- Works without sending audio to a cloud API
- Selectable Vosk model path
- Selectable audio input device
- Configurable sample rate
- Timestamped transcript output
- Optional confidence score per transcription line
- Scanner-specific correction rules
- Works with Windows audio inputs such as:
  - microphone
  - Stereo Mix
  - virtual audio cable
  - loopback-style routing, depending on setup

## Planned Features

### CLI Version

- Interactive startup prompts
- Filtered list of usable input devices
- Session name prompt
- Cleaner filename generation
- Optional WAV recording
- Separate raw and cleaned transcript files
- Better correction-rule management
- Keyword detection
- Local desktop notifications

### GUI Version

- Audio device dropdown
- Model selection
- Sample-rate selection
- Live cleaned transcript window
- Live raw transcript window
- Correction-rule editor
- Keyword list editor
- Start/stop buttons
- Save-location selection

### Notification Version

- Keyword detection
- Desktop notification
- Sound alert
- Email notification
- Possibly SMS or push notification later

## How It Works

The basic pipeline is:

```text
Audio source
    ↓
Windows audio input
    ↓
Python sounddevice stream
    ↓
Vosk speech recognizer
    ↓
Raw transcript
    ↓
Scanner cleanup rules
    ↓
Clean transcript file