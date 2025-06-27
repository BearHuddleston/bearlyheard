# BearlyHeard - Meeting Recorder Application Specification

## Project Overview

BearlyHeard is an all-in-one GUI application for recording, transcribing, and summarizing meetings. It captures audio from both application sources (like Microsoft Teams) and microphone input simultaneously, providing automated transcription using Whisper and AI-powered summarization using LLMs.

## Key Features

### Core Functionality
- **Dual Audio Recording**: Simultaneous capture of application audio (Teams, Zoom, etc.) and microphone input
- **Automatic Transcription**: Local, offline transcription using OpenAI Whisper
- **AI Summarization**: Generate meeting summaries and extract action items using LLMs
- **Speaker Diarization**: Identify and separate different speakers in the recording
- **File Management**: Organized storage with metadata tracking

### User Interface
- Modern PyQt6 GUI with dark/light theme support
- One-click recording with visual feedback
- Real-time audio level monitoring
- Recent recordings list with quick actions
- Progress indicators for transcription/summarization

## Technical Architecture

### Technology Stack
- **Language**: Python 3.10+
- **Package Manager**: uv (with virtual environment)
- **GUI Framework**: PyQt6 with PyQtDarkTheme
- **Audio Libraries**:
  - PyAudioWPatch (Windows system audio capture)
  - python-sounddevice (microphone recording)
- **ML/AI Libraries**:
  - OpenAI Whisper (transcription)
  - llama-cpp-python (summarization)
  - pyannote.audio (speaker diarization)
- **Utilities**:
  - pydub (audio processing)
  - python-docx & reportlab (document export)

### Project Structure
```
bearlyheard/
├── src/
│   ├── main.py              # Application entry point
│   ├── audio/
│   │   ├── capture.py       # Audio recording logic
│   │   ├── mixer.py         # Dual-source mixing
│   │   └── devices.py       # Device enumeration
│   ├── gui/
│   │   ├── main_window.py   # Main application window
│   │   ├── dialogs.py       # Dialog windows
│   │   ├── widgets.py       # Custom widgets
│   │   └── themes.py        # Theme management
│   ├── ml/
│   │   ├── transcriber.py   # Whisper integration
│   │   ├── summarizer.py    # LLM integration
│   │   └── diarizer.py      # Speaker separation
│   └── utils/
│       ├── file_manager.py  # File operations
│       ├── config.py        # Settings management
│       └── logger.py        # Logging utilities
├── models/                  # ML model storage
├── resources/               # Icons and styles
└── tests/                   # Test suite
```

## Detailed Specifications

### Audio Capture Module

#### Requirements
- Capture system audio from specific applications (Teams, Zoom, etc.)
- Simultaneously record microphone input
- Mix audio streams in real-time
- Save as WAV format with configurable quality
- Monitor audio levels for visual feedback

#### Implementation Details
- Use PyAudioWPatch for WASAPI loopback on Windows
- Implement ring buffer for real-time mixing
- Support multiple audio formats (16-bit, 24-bit, 44.1kHz, 48kHz)
- Handle device disconnection gracefully

### GUI Design

#### Main Window Layout
```
┌─────────────────────────────────────────┐
│  BearlyHeard - Meeting Recorder     [─][□][×]│
├─────────────────────────────────────────┤
│  Audio Sources:                         │
│  ┌─────────────────────────────────┐   │
│  │ Application: [Teams        ▼]   │   │
│  │ Microphone:  [Default Mic  ▼]   │   │
│  └─────────────────────────────────┘   │
│                                         │
│  ┌─────────────────────────────────┐   │
│  │      [●] Record / [■] Stop      │   │
│  │         00:00:00                │   │
│  │    ▁▃▅▇▅▃▁ Audio Levels        │   │
│  └─────────────────────────────────┘   │
│                                         │
│  Status: Ready to record               │
│                                         │
│  Recent Recordings:                     │
│  ┌─────────────────────────────────┐   │
│  │ 📁 Meeting_2024-01-15_14-30.wav │   │
│  │    [▶ Play] [📝 Transcribe]     │   │
│  │    [📊 Summarize] [🗑 Delete]   │   │
│  └─────────────────────────────────┘   │
└─────────────────────────────────────────┘
```

#### Dialog Windows
1. **Post-Recording Dialog**
   - Options: Transcribe Now / Save Only / Discard
   - Shows recording duration and file size

2. **Transcription Progress**
   - Progress bar with percentage
   - Estimated time remaining
   - Cancel option

3. **Settings Dialog**
   - Audio quality settings
   - Model selection (Whisper size, LLM model)
   - File storage location
   - Theme selection

### Transcription System

#### Whisper Integration
- Support multiple model sizes (tiny, base, small, medium, large)
- Automatic language detection
- Timestamp generation for each segment
- Background processing with progress callbacks
- Error handling for corrupted audio

#### Output Format
```
[00:00:00] Speaker 1: Welcome everyone to today's meeting.
[00:00:05] Speaker 2: Thanks for joining. Let's get started.
[00:00:10] Speaker 1: First item on the agenda...
```

### Summarization Engine

#### LLM Integration
- Use llama-cpp-python for local inference
- Support various models (Mistral, Llama, etc.)
- Customizable prompts for different summary types

#### Summary Templates
1. **Executive Summary**
   - Key decisions made
   - Action items with owners
   - Next steps

2. **Detailed Minutes**
   - Topic-by-topic breakdown
   - Discussion points
   - Decisions and rationale

3. **Action Items Only**
   - Task description
   - Assigned to
   - Due date (if mentioned)

### File Management

#### Directory Structure
```
~/Documents/BearlyHeard/
├── recordings/
│   ├── 2024-01-15_14-30-00_meeting.wav
│   └── metadata.json
├── transcripts/
│   └── 2024-01-15_14-30-00_transcript.txt
├── summaries/
│   └── 2024-01-15_14-30-00_summary.md
└── exports/
    └── 2024-01-15_14-30-00_minutes.pdf
```

#### Metadata Format
```json
{
  "recording_id": "2024-01-15_14-30-00",
  "duration": "00:45:30",
  "participants": ["Speaker 1", "Speaker 2"],
  "audio_sources": {
    "application": "Microsoft Teams",
    "microphone": "Blue Yeti USB"
  },
  "transcription": {
    "model": "whisper-base",
    "language": "en",
    "completed": "2024-01-15T15:20:00"
  },
  "summary": {
    "model": "mistral-7b",
    "type": "executive",
    "completed": "2024-01-15T15:25:00"
  }
}
```

## User Workflows

### Recording Workflow
1. User launches application
2. Selects audio sources (application + microphone)
3. Clicks Record button
4. Visual feedback shows recording in progress
5. User clicks Stop when meeting ends
6. Post-recording dialog appears
7. User chooses action (transcribe/save/discard)

### Transcription Workflow
1. Automatic after recording (if selected)
2. Or manual from recent recordings list
3. Progress bar shows transcription status
4. Transcript displayed in viewer
5. Option to edit/correct transcript
6. Save with timestamps

### Summarization Workflow
1. Available after transcription completes
2. User selects summary type
3. LLM processes transcript
4. Summary displayed for review
5. User can regenerate with different prompts
6. Export to various formats

## Development Milestones

### Phase 1: Core Audio (Week 1-2)
- [ ] Basic PyQt6 application window
- [ ] Audio device enumeration
- [ ] Single-source recording (microphone)
- [ ] WAV file saving

### Phase 2: Dual Recording (Week 3-4)
- [ ] PyAudioWPatch integration
- [ ] Application audio capture
- [ ] Audio mixing implementation
- [ ] Recording controls UI

### Phase 3: Transcription (Week 5-6)
- [ ] Whisper model integration
- [ ] Background processing
- [ ] Transcript viewer UI
- [ ] Basic file management

### Phase 4: Summarization (Week 7-8)
- [ ] LLM integration
- [ ] Summary generation
- [ ] Multiple summary templates
- [ ] Export functionality

### Phase 5: Polish (Week 9-10)
- [ ] Speaker diarization
- [ ] Dark/light themes
- [ ] Settings persistence
- [ ] Installer creation
- [ ] Testing and optimization

## Security & Privacy

- All processing happens locally (no cloud services)
- Audio files encrypted at rest (optional)
- Automatic cleanup of old recordings (configurable)
- No telemetry or data collection

## Performance Targets

- Recording: < 5% CPU usage
- Transcription: < 2x real-time on CPU
- Summarization: < 30 seconds for 1-hour meeting
- Memory usage: < 500MB during recording
- Startup time: < 3 seconds

## Future Enhancements

- Real-time transcription during recording
- Multi-language support
- Cloud backup integration (optional)
- Team collaboration features
- Mobile companion app
- Calendar integration
- Custom vocabulary support