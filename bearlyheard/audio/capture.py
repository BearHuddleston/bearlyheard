"""Audio capture implementation for BearlyHeard"""

import threading
import time
import wave
from pathlib import Path
from typing import Optional, Callable, List, Dict, Any
from dataclasses import dataclass

try:
    import sounddevice as sd
    import numpy as np
    HAS_SOUNDDEVICE = True
except (ImportError, OSError):
    sd = None
    np = None
    HAS_SOUNDDEVICE = False

from .devices import AudioDevice, AudioDeviceManager
from .applications import AudioApplication
from .app_recorder import ApplicationAudioRecorder
from .wasapi_capture import WASAPIApplicationRecorder
from ..utils.logger import LoggerMixin


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
        self.device_manager = AudioDeviceManager()  # Initialize device_manager
        self.microphone_recorder = None
        self.application_recorder = None
        self.default_sample_rate = 44100  # Default/fallback sample rate
        self.actual_sample_rate = 44100   # Will be updated based on devices
        self.channels = 2
        self.is_recording = False
        self.output_file = None
        self.level_callbacks = []
        
        self.logger.info("AudioCapture initialized")
    
    def _determine_optimal_sample_rate(self):
        """Determine the optimal sample rate based on selected devices"""
        sample_rates = []
        
        # Check microphone device sample rate
        if self.microphone_recorder and hasattr(self.microphone_recorder, 'device') and self.microphone_recorder.device:
            # For now, assume microphone uses default sample rate
            # In a real implementation, we'd query the device
            sample_rates.append(self.default_sample_rate)
        
        # Check application recorder sample rate
        if self.application_recorder:
            if hasattr(self.application_recorder, 'actual_sample_rate'):
                sample_rates.append(self.application_recorder.actual_sample_rate)
            else:
                # Fallback: check if it's a WASAPI recorder with loopback devices
                loopback_devices = self.device_manager.get_loopback_devices()
                if loopback_devices:
                    # Most loopback devices use 48kHz
                    sample_rates.append(48000)
        
        if sample_rates:
            # Use the highest sample rate to avoid quality loss
            self.actual_sample_rate = max(sample_rates)
            self.logger.info(f"Determined optimal sample rate: {self.actual_sample_rate}Hz from rates: {sample_rates}")
        else:
            self.actual_sample_rate = self.default_sample_rate
            self.logger.info(f"Using default sample rate: {self.actual_sample_rate}Hz")
    
    def set_microphone_device(self, device: Optional[AudioDevice]):
        """Set microphone device"""
        if self.is_recording:
            self.logger.warning("Cannot change device while recording")
            return
        
        self.microphone_recorder = AudioRecorder(device, self.actual_sample_rate, self.channels)
        if device:
            self.logger.info(f"Set microphone device: {device.name}")
        
        # Update sample rate after setting devices
        self._determine_optimal_sample_rate()
    
    def set_application(self, application: Optional[AudioApplication]):
        """Set application audio"""
        if self.is_recording:
            self.logger.warning("Cannot change application while recording")
            return
        
        if application:
            # First, determine what sample rate the loopback devices use
            loopback_devices = self.device_manager.get_loopback_devices()
            if loopback_devices:
                # Find the best loopback device (prioritize SteelSeries Sonar Gaming)
                best_device = None
                for device in loopback_devices:
                    if "steelseries sonar" in device.name.lower() and "gaming" in device.name.lower():
                        best_device = device
                        break
                
                # Fallback to any SteelSeries Sonar device
                if not best_device:
                    for device in loopback_devices:
                        if "steelseries sonar" in device.name.lower():
                            best_device = device
                            break
                
                # Final fallback to first available loopback device
                if not best_device:
                    best_device = loopback_devices[0]
                
                # Use the device's actual sample rate
                old_sample_rate = self.actual_sample_rate
                
                # Try to get the device's default sample rate
                try:
                    import pyaudiowpatch as pyaudio
                    pa = pyaudio.PyAudio()
                    
                    # Find the device index for this device
                    device_index = None
                    for i in range(pa.get_device_count()):
                        device_info = pa.get_device_info_by_index(i)
                        if device_info['name'] == best_device.name:
                            device_index = i
                            self.actual_sample_rate = int(device_info['defaultSampleRate'])
                            break
                    
                    pa.terminate()
                    
                    if device_index is not None:
                        self.logger.info(f"Using {best_device.name} at {self.actual_sample_rate}Hz")
                    else:
                        self.actual_sample_rate = 48000  # Fallback
                        self.logger.warning(f"Could not find device index for {best_device.name}, using 48kHz fallback")
                        
                except Exception as e:
                    self.logger.error(f"Error detecting device sample rate: {e}")
                    self.actual_sample_rate = 48000  # Fallback
                
                # Update microphone recorder if sample rate changed
                if old_sample_rate != self.actual_sample_rate and self.microphone_recorder:
                    mic_device = self.microphone_recorder.device if hasattr(self.microphone_recorder, 'device') else None
                    self.microphone_recorder = AudioRecorder(mic_device, self.actual_sample_rate, self.channels)
                    self.logger.info(f"Updated microphone recorder to {self.actual_sample_rate}Hz")
            
            # Use WASAPI for true application-specific audio capture
            self.application_recorder = WASAPIApplicationRecorder(application, self.actual_sample_rate, self.channels)
            self.logger.info(f"Set application: {application.name} (using WASAPI at {self.actual_sample_rate}Hz)")
            self.logger.info("Using Windows Audio Session API for application-specific capture")
        else:
            self.application_recorder = None
            # Reset to default sample rate if no application
            old_sample_rate = self.actual_sample_rate
            self.actual_sample_rate = self.default_sample_rate
            
            # Update microphone recorder if sample rate changed
            if old_sample_rate != self.actual_sample_rate and self.microphone_recorder:
                mic_device = self.microphone_recorder.device if hasattr(self.microphone_recorder, 'device') else None
                self.microphone_recorder = AudioRecorder(mic_device, self.actual_sample_rate, self.channels)
                self.logger.info(f"Reset microphone recorder to {self.actual_sample_rate}Hz")
    
    def set_application_device(self, device: Optional[AudioDevice]):
        """Set application audio device (backward compatibility)"""
        if self.is_recording:
            self.logger.warning("Cannot change device while recording")
            return
        
        if device:
            # For device-based recording, use the original AudioRecorder
            self.application_recorder = AudioRecorder(device, self.actual_sample_rate, self.channels)
            self.logger.info(f"Set application device: {device.name}")
        else:
            self.application_recorder = None
        
        # Update sample rate after setting devices
        self._determine_optimal_sample_rate()
    
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
                wav_file.setframerate(self.actual_sample_rate)
                
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
            return total_frames / self.actual_sample_rate
        
        return 0.0