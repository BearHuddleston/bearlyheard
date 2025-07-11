# BearlyHeard =;<�

An all-in-one desktop application for recording, transcribing, and summarizing meetings with AI-powered insights.

## Features

- <� **Dual Audio Recording** - Capture both system audio (Teams, Zoom) and microphone simultaneously
- > **AI Transcription** - Local, offline transcription using OpenAI Whisper
- =� **Smart Summaries** - Generate meeting summaries and extract action items with LLMs
- =e **Speaker Recognition** - Identify and separate different speakers
- <� **Modern UI** - Clean PyQt6 interface with dark/light themes
- = **Privacy First** - All processing happens locally, no cloud dependencies

## Quick Start

### Prerequisites
- Python 3.10 or higher
- Windows 10/11 (for system audio capture)
- [uv](https://github.com/astral-sh/uv) package manager

### Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/bearlyheard.git
cd bearlyheard
```

2. Install dependencies using uv:
```bash
uv sync
```

3. Run the application:
```bash
uv run python src/main.py
```

## Usage

1. **Select Audio Sources**
   - Choose your application (e.g., Microsoft Teams)
   - Select your microphone device

2. **Start Recording**
   - Click the Record button to begin
   - Audio levels show real-time feedback

3. **Stop and Process**
   - Click Stop when your meeting ends
   - Choose to transcribe immediately or save for later

4. **Review Results**
   - View the transcript with timestamps
   - Generate AI-powered summaries
   - Export to various formats (PDF, DOCX, TXT)

## Development

### Setting up the development environment

```bash
# Clone the repo
git clone https://github.com/yourusername/bearlyheard.git
cd bearlyheard

# Install dependencies
uv sync

# Run tests
uv run pytest

# Run the application in development mode
uv run python src/main.py --debug
```

### Project Structure

```
bearlyheard/
   src/
      audio/      # Audio capture and processing
      gui/        # PyQt6 user interface
      ml/         # AI/ML integrations
      utils/      # Helper utilities
   models/         # ML model storage
   resources/      # Icons and styles
   tests/          # Test suite
```

## Configuration

BearlyHeard stores configuration in `~/.bearlyheard/config.json`. You can customize:

- Audio quality settings
- Whisper model size (tiny, base, small, medium, large)
- LLM model selection
- File storage locations
- UI theme preferences

## Models

On first run, BearlyHeard will download the required models:

- **Whisper**: Speech-to-text model (size varies by selection)
- **LLM**: Language model for summarization (e.g., Mistral 7B)

Models are stored locally in the `models/` directory.

## Contributing

We welcome contributions! Please see our [Contributing Guide](CONTRIBUTING.md) for details.

### Development Progress

**Phase 1: Foundation (✅ Complete)**
- [x] Project setup with uv package manager
- [x] Core utilities (logging, config, file management)
- [x] Audio device management
- [x] Theme system with dark/light modes
- [x] Main GUI window with recording interface

**Phase 2: Audio Implementation (✅ Complete)**
- [x] Dual audio capture (system + microphone)
- [x] Real-time audio mixing
- [x] WAV file recording
- [x] Audio level monitoring
- [x] Audio playback functionality

**Phase 3: AI Integration (✅ Complete)**
- [x] Whisper transcription integration with faster-whisper
- [x] LLM summarization with llama.cpp
- [x] Background processing with worker threads
- [x] Progress tracking and UI integration
- [x] Transcript viewer and editor
- [x] Export functionality

**Phase 4: Advanced Features (📋 Planned)**
- [ ] Export to multiple formats
- [ ] Real-time transcription
- [ ] Settings dialog
- [ ] Installer creation

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- [OpenAI Whisper](https://github.com/openai/whisper) for transcription
- [llama.cpp](https://github.com/ggerganov/llama.cpp) for local LLM inference
- [PyAudioWPatch](https://github.com/s0d3s/PyAudioWPatch) for Windows audio capture
- [pyannote.audio](https://github.com/pyannote/pyannote-audio) for speaker diarization

## Support

For issues, questions, or suggestions:
- Open an issue on [GitHub](https://github.com/yourusername/bearlyheard/issues)
- Check the [Wiki](https://github.com/yourusername/bearlyheard/wiki) for detailed documentation

---

Made with d for better meeting productivity