"""Audio capture implementation for BearlyHeard"""

import threading
import time
import wave
from pathlib import Path
from typing import Optional, Callable, List
from dataclasses import dataclass

try:
    import sounddevice as sd
    import numpy as np
    HAS_SOUNDDEVICE = True
except (ImportError, OSError):
    sd = None
    np = None
    HAS_SOUNDDEVICE = False

from ..utils.logger import LoggerMixin
from .devices import AudioDevice


@dataclass
class AudioLevel:
    """Audio level information"""
    rms: float
    peak: float
    timestamp: float


class AudioRecorder(LoggerMixin):
    """Single audio source recorder"""
    
    def __init__(self, device: Optional[AudioDevice], sample_rate: int = 44100, channels: int = 2):
        """
        Initialize audio recorder
        
        Args:
            device: Audio device to record from
            sample_rate: Sample rate in Hz
            channels: Number of channels
        """
        self.device = device
        self.sample_rate = sample_rate
        self.channels = channels
        self.is_recording = False
        self.audio_data = []
        self.stream = None
        self.audio_levels = []
        self.level_callback = None
        
        if not HAS_SOUNDDEVICE:
            self.logger.warning("sounddevice not available, recording disabled")
    
    def set_level_callback(self, callback: Callable[[AudioLevel], None]):
        """Set callback for audio level updates"""
        self.level_callback = callback
    
    def start_recording(self) -> bool:
        """Start recording audio"""
        if not HAS_SOUNDDEVICE:
            self.logger.error("Cannot record: sounddevice not available")
            return False
        
        if self.is_recording:
            self.logger.warning("Already recording")
            return False
        
        try:
            self.audio_data = []
            self.audio_levels = []
            
            # Determine device index
            device_index = None
            if self.device and self.device.index < 1000:  # sounddevice device
                device_index = self.device.index
            
            # Start recording stream
            self.stream = sd.InputStream(
                samplerate=self.sample_rate,
                channels=self.channels,
                device=device_index,
                callback=self._audio_callback,
                blocksize=1024
            )
            
            self.stream.start()
            self.is_recording = True
            
            device_name = self.device.name if self.device else "default"
            self.logger.info(f"Started recording from {device_name}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to start recording: {e}")
            return False
    
    def stop_recording(self) -> bool:
        """Stop recording audio"""
        if not self.is_recording:
            return True
        
        try:
            if self.stream:
                self.stream.stop()
                self.stream.close()
                self.stream = None
            
            self.is_recording = False
            self.logger.info("Stopped recording")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to stop recording: {e}")
            return False
    
    def get_audio_data(self):
        """Get recorded audio data"""
        if not HAS_SOUNDDEVICE or not self.audio_data:
            return None
        
        try:
            return np.concatenate(self.audio_data, axis=0)
        except Exception as e:
            self.logger.error(f"Failed to get audio data: {e}")
            return None
    
    def _audio_callback(self, indata, frames, time, status):
        """Audio stream callback"""
        if status:
            self.logger.warning(f"Audio callback status: {status}")
        
        # Store audio data
        if indata is not None:
            self.audio_data.append(indata.copy())
            
            # Calculate audio levels
            if self.level_callback:
                try:
                    # Calculate RMS and peak levels
                    rms = np.sqrt(np.mean(indata**2))
                    peak = np.max(np.abs(indata))
                    
                    level = AudioLevel(
                        rms=float(rms),
                        peak=float(peak),
                        timestamp=time.inputBufferAdcTime
                    )
                    
                    self.audio_levels.append(level)
                    self.level_callback(level)
                    
                except Exception as e:
                    self.logger.debug(f"Error calculating audio levels: {e}")


class AudioCapture(LoggerMixin):
    """Multi-source audio capture system"""
    
    def __init__(self):
        """Initialize audio capture system"""
        self.microphone_recorder = None
        self.application_recorder = None
        self.sample_rate = 44100
        self.channels = 2
        self.is_recording = False
        self.output_file = None
        self.level_callbacks = []
        
        self.logger.info("AudioCapture initialized")
    
    def set_microphone_device(self, device: Optional[AudioDevice]):
        """Set microphone device"""
        if self.is_recording:
            self.logger.warning("Cannot change device while recording")
            return
        
        self.microphone_recorder = AudioRecorder(device, self.sample_rate, self.channels)
        if device:
            self.logger.info(f"Set microphone device: {device.name}")
    
    def set_application_device(self, device: Optional[AudioDevice]):
        """Set application audio device"""
        if self.is_recording:
            self.logger.warning("Cannot change device while recording")
            return
        
        self.application_recorder = AudioRecorder(device, self.sample_rate, self.channels)
        if device:
            self.logger.info(f"Set application device: {device.name}")
    
    def add_level_callback(self, callback: Callable[[str, AudioLevel], None]):
        """Add callback for audio level updates"""
        self.level_callbacks.append(callback)
    
    def start_recording(self, output_file: str) -> bool:
        """
        Start recording audio from configured sources
        
        Args:
            output_file: Path to output WAV file
            
        Returns:
            True if recording started successfully
        """
        if self.is_recording:
            self.logger.warning("Already recording")
            return False
        
        if not self.microphone_recorder and not self.application_recorder:
            self.logger.error("No audio sources configured")
            return False
        
        self.output_file = Path(output_file)
        
        # Setup level callbacks
        if self.microphone_recorder:
            self.microphone_recorder.set_level_callback(
                lambda level: self._on_level_update("microphone", level)
            )
        
        if self.application_recorder:
            self.application_recorder.set_level_callback(
                lambda level: self._on_level_update("application", level)
            )
        
        # Start recording from all sources
        success = True
        
        if self.microphone_recorder:
            if not self.microphone_recorder.start_recording():
                success = False
        
        if self.application_recorder and success:
            if not self.application_recorder.start_recording():
                # Stop microphone if application fails
                if self.microphone_recorder:
                    self.microphone_recorder.stop_recording()
                success = False
        
        if success:
            self.is_recording = True
            self.logger.info(f"Started recording to {output_file}")
        else:
            self.logger.error("Failed to start all recording sources")
        
        return success
    
    def stop_recording(self) -> bool:
        """
        Stop recording and save to file
        
        Returns:
            True if recording stopped and saved successfully
        """
        if not self.is_recording:
            return True
        
        # Stop all recorders
        mic_success = True
        app_success = True
        
        if self.microphone_recorder:
            mic_success = self.microphone_recorder.stop_recording()
        
        if self.application_recorder:
            app_success = self.application_recorder.stop_recording()
        
        self.is_recording = False
        
        # Save recorded audio
        if mic_success or app_success:
            return self._save_audio_file()
        
        return False
    
    def _save_audio_file(self) -> bool:
        """Save recorded audio to WAV file"""
        if not self.output_file:
            self.logger.error("No output file specified")
            return False
        
        try:
            # Get audio data from recorders
            mic_data = None
            app_data = None
            
            if self.microphone_recorder:
                mic_data = self.microphone_recorder.get_audio_data()
            
            if self.application_recorder:
                app_data = self.application_recorder.get_audio_data()
            
            # Mix audio sources
            mixed_audio = self._mix_audio_sources(mic_data, app_data)
            
            if mixed_audio is None:
                self.logger.error("No audio data to save")
                return False
            
            # Ensure output directory exists
            self.output_file.parent.mkdir(parents=True, exist_ok=True)
            
            # Save as WAV file
            with wave.open(str(self.output_file), 'wb') as wav_file:
                wav_file.setnchannels(self.channels)
                wav_file.setsampwidth(2)  # 16-bit
                wav_file.setframerate(self.sample_rate)
                
                # Convert to 16-bit integers
                audio_int16 = (mixed_audio * 32767).astype(np.int16)
                wav_file.writeframes(audio_int16.tobytes())
            
            file_size = self.output_file.stat().st_size
            self.logger.info(f"Saved recording: {self.output_file} ({file_size} bytes)")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to save audio file: {e}")
            return False
    
    def _mix_audio_sources(self, mic_data, app_data):
        """Mix microphone and application audio"""
        if not HAS_SOUNDDEVICE:
            return None
        
        # If only one source, return it directly
        if mic_data is not None and app_data is None:
            return mic_data
        elif app_data is not None and mic_data is None:
            return app_data
        elif mic_data is None and app_data is None:
            return None
        
        # Mix both sources
        try:
            # Ensure both have same length
            min_length = min(len(mic_data), len(app_data))
            mic_trimmed = mic_data[:min_length]
            app_trimmed = app_data[:min_length]
            
            # Simple mixing: average the two sources
            mixed = (mic_trimmed + app_trimmed) / 2.0
            
            # Prevent clipping
            max_val = np.max(np.abs(mixed))
            if max_val > 1.0:
                mixed = mixed / max_val
            
            return mixed
            
        except Exception as e:
            self.logger.error(f"Failed to mix audio sources: {e}")
            return mic_data if mic_data is not None else app_data
    
    def _on_level_update(self, source: str, level: AudioLevel):
        """Handle audio level update"""
        for callback in self.level_callbacks:
            try:
                callback(source, level)
            except Exception as e:
                self.logger.debug(f"Error in level callback: {e}")
    
    def get_recording_duration(self) -> float:
        """Get current recording duration in seconds"""
        if not self.is_recording:
            return 0.0
        
        # Estimate duration based on audio data
        if self.microphone_recorder and self.microphone_recorder.audio_data:
            total_frames = sum(len(chunk) for chunk in self.microphone_recorder.audio_data)
            return total_frames / self.sample_rate
        
        return 0.0