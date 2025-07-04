"""Transcription implementation for BearlyHeard"""

import os
from pathlib import Path
from typing import Optional, Dict, Any, Callable, List
from dataclasses import dataclass

try:
    from faster_whisper import WhisperModel
    HAS_WHISPER = True
except ImportError:
    HAS_WHISPER = False

from ..utils.logger import LoggerMixin


@dataclass
class TranscriptionSegment:
    """Transcription segment with timing"""
    start: float
    end: float
    text: str
    confidence: float = 0.0


@dataclass
class TranscriptionResult:
    """Complete transcription result"""
    text: str
    segments: List[TranscriptionSegment]
    language: str
    duration: float
    model_name: str


class Transcriber(LoggerMixin):
    """Audio transcription using Faster-Whisper"""
    
    def __init__(self, model_size: str = "base", device: str = "cpu"):
        """
        Initialize transcriber
        
        Args:
            model_size: Whisper model size (tiny, base, small, medium, large-v3)
            device: Device to run on (cpu, cuda)
        """
        self.model_size = model_size
        self.device = device
        self.model = None
        self.is_loaded = False
        self.progress_callback = None
        
        if not HAS_WHISPER:
            self.logger.warning("faster-whisper not available, transcription disabled")
        else:
            self.logger.info(f"Transcriber initialized with model: {model_size}")
    
    def load_model(self) -> bool:
        """
        Load the Whisper model
        
        Returns:
            True if model loaded successfully
        """
        if not HAS_WHISPER:
            self.logger.error("Cannot load model: faster-whisper not available")
            return False
        
        if self.is_loaded:
            self.logger.debug("Model already loaded")
            return True
        
        try:
            self.logger.info(f"Loading Whisper model: {self.model_size} on {self.device}")
            
            # Load model with CPU optimization
            compute_type = "int8" if self.device == "cpu" else "float16"
            self.logger.debug(f"Using compute_type: {compute_type}")
            
            self.model = WhisperModel(
                self.model_size,
                device=self.device,
                compute_type=compute_type
            )
            
            self.is_loaded = True
            self.logger.info(f"Whisper model {self.model_size} loaded successfully")
            
            # Test the model with a simple call to ensure it's working
            try:
                # This will help catch any issues with the model after loading
                self.logger.debug("Testing model functionality...")
                # We don't actually call transcribe here, just verify the model object is valid
                if hasattr(self.model, 'transcribe'):
                    self.logger.debug("Model appears to be functional")
                else:
                    self.logger.warning("Model loaded but transcribe method not found")
            except Exception as test_e:
                self.logger.warning(f"Model loaded but test failed: {test_e}")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to load Whisper model {self.model_size}: {type(e).__name__}: {e}")
            import traceback
            self.logger.debug(f"Model loading error traceback: {traceback.format_exc()}")
            self.is_loaded = False
            self.model = None
            return False
    
    def set_progress_callback(self, callback: Callable[[float], None]):
        """Set callback for progress updates"""
        self.progress_callback = callback
    
    def transcribe(
        self,
        audio_file: str,
        language: Optional[str] = None,
        task: str = "transcribe"
    ) -> Optional[TranscriptionResult]:
        """
        Transcribe audio file
        
        Args:
            audio_file: Path to audio file
            language: Language code (auto-detect if None)
            task: Task type (transcribe or translate)
            
        Returns:
            Transcription result or None if failed
        """
        if not HAS_WHISPER:
            self.logger.error("Cannot transcribe: faster-whisper not available")
            return self._create_placeholder_result(audio_file)
        
        audio_path = Path(audio_file)
        if not audio_path.exists():
            self.logger.error(f"Audio file not found: {audio_file}")
            return None
        
        # Check if audio file is empty or too small
        file_size = audio_path.stat().st_size
        if file_size < 1024:  # Less than 1KB
            self.logger.error(f"Audio file too small ({file_size} bytes): {audio_file}")
            return None
        
        # Load model if not already loaded
        if not self.load_model():
            self.logger.error("Failed to load Whisper model")
            return None
        
        try:
            self.logger.info(f"Starting transcription of {audio_file} (size: {file_size} bytes)")
            
            # Call progress callback for start
            if self.progress_callback:
                self.progress_callback(0.0)
            
            # Transcribe audio
            self.logger.debug("Calling Whisper model.transcribe()")
            
            # Try with VAD filter first, fallback to no VAD if it fails
            transcribe_params = {
                "language": language,
                "task": task,
                "beam_size": 5,
                "best_of": 5,
                "temperature": 0.0,
                "condition_on_previous_text": False,
            }
            
            try:
                # First attempt with VAD filter
                segments, info = self.model.transcribe(
                    str(audio_path),
                    vad_filter=True,
                    vad_parameters=dict(min_silence_duration_ms=500),
                    **transcribe_params
                )
                self.logger.debug("Transcription completed with VAD filter")
            except RuntimeError as e:
                if "VAD filter" in str(e) or "onnxruntime" in str(e):
                    self.logger.warning(f"VAD filter failed ({e}), retrying without VAD filter")
                    # Retry without VAD filter
                    segments, info = self.model.transcribe(
                        str(audio_path),
                        vad_filter=False,
                        **transcribe_params
                    )
                    self.logger.debug("Transcription completed without VAD filter")
                else:
                    raise  # Re-raise if it's a different RuntimeError
            
            self.logger.debug(f"Whisper returned info: language={info.language}, duration={getattr(info, 'duration', 'unknown')}")
            
            # Process segments
            transcription_segments = []
            full_text = ""
            segment_count = 0
            
            for i, segment in enumerate(segments):
                segment_count += 1
                # Call progress callback
                if self.progress_callback:
                    progress = min(1.0, (i + 1) / 100)  # Estimate progress
                    self.progress_callback(progress)
                
                seg = TranscriptionSegment(
                    start=segment.start,
                    end=segment.end,
                    text=segment.text.strip(),
                    confidence=getattr(segment, 'avg_logprob', 0.0)
                )
                
                transcription_segments.append(seg)
                full_text += seg.text + " "
                
                # Log first few segments for debugging
                if i < 3:
                    self.logger.debug(f"Segment {i}: [{seg.start:.2f}-{seg.end:.2f}] '{seg.text}'")
            
            # Final progress update
            if self.progress_callback:
                self.progress_callback(1.0)
            
            # Check if we got any segments
            if not transcription_segments:
                self.logger.warning(f"No transcription segments found for {audio_file}. Audio might be silent or too short.")
                # Return empty result instead of None
                return TranscriptionResult(
                    text="[No speech detected]",
                    segments=[],
                    language=info.language if info else "unknown",
                    duration=0.0,
                    model_name=f"whisper-{self.model_size}"
                )
            
            # Calculate duration
            duration = transcription_segments[-1].end if transcription_segments else 0.0
            
            result = TranscriptionResult(
                text=full_text.strip(),
                segments=transcription_segments,
                language=info.language,
                duration=duration,
                model_name=f"whisper-{self.model_size}"
            )
            
            self.logger.info(f"Transcription completed: {len(transcription_segments)} segments, "
                           f"{duration:.2f}s duration, language: {info.language}")
            
            return result
            
        except Exception as e:
            self.logger.error(f"Failed to transcribe {audio_file}: {type(e).__name__}: {e}")
            import traceback
            self.logger.debug(f"Transcription error traceback: {traceback.format_exc()}")
            return None
    
    def transcribe_with_timestamps(
        self,
        audio_file: str,
        language: Optional[str] = None
    ) -> Optional[str]:
        """
        Transcribe audio file and return formatted text with timestamps
        
        Args:
            audio_file: Path to audio file
            language: Language code (auto-detect if None)
            
        Returns:
            Formatted transcript with timestamps or None if failed
        """
        result = self.transcribe(audio_file, language)
        if not result:
            return None
        
        try:
            formatted_text = ""
            for segment in result.segments:
                start_time = self._format_timestamp(segment.start)
                formatted_text += f"[{start_time}] {segment.text}\n"
            
            return formatted_text
            
        except Exception as e:
            self.logger.error(f"Failed to format transcript: {e}")
            return result.text if result else None
    
    def _format_timestamp(self, seconds: float) -> str:
        """Format seconds as MM:SS timestamp"""
        minutes = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{minutes:02d}:{secs:02d}"
    
    def _create_placeholder_result(self, audio_file: str) -> TranscriptionResult:
        """Create placeholder result when Whisper is not available"""
        return TranscriptionResult(
            text="Transcription not available (faster-whisper not installed)",
            segments=[
                TranscriptionSegment(
                    start=0.0,
                    end=5.0,
                    text="Transcription not available (faster-whisper not installed)",
                    confidence=0.0
                )
            ],
            language="en",
            duration=5.0,
            model_name="placeholder"
        )
    
    def get_available_models(self) -> List[str]:
        """Get list of available model sizes"""
        return ["tiny", "base", "small", "medium", "large-v3"]
    
    def get_supported_languages(self) -> List[str]:
        """Get list of supported language codes"""
        # Common languages supported by Whisper
        return [
            "en", "es", "fr", "de", "it", "pt", "nl", "pl", "tr", "ru",
            "ja", "ko", "zh", "ar", "hi", "th", "vi", "id", "ms", "ur"
        ]
    
    def estimate_processing_time(self, audio_duration: float) -> float:
        """
        Estimate processing time based on audio duration and model size
        
        Args:
            audio_duration: Audio duration in seconds
            
        Returns:
            Estimated processing time in seconds
        """
        # Rough estimates based on model size (CPU)
        multipliers = {
            "tiny": 0.1,
            "base": 0.2,
            "small": 0.4,
            "medium": 0.8,
            "large-v3": 1.5
        }
        
        multiplier = multipliers.get(self.model_size, 0.5)
        return audio_duration * multiplier
    
    def clear_model(self):
        """Clear the loaded model to free memory"""
        if self.model:
            del self.model
            self.model = None
            self.is_loaded = False
            self.logger.info("Whisper model cleared from memory")