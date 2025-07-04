"""Application-specific audio recording for BearlyHeard"""

import threading
import time
import wave
import numpy as np
from typing import Optional, Callable, List
from pathlib import Path

try:
    import pyaudiowpatch as pyaudio
    HAS_PYAUDIO = True
except ImportError:
    pyaudio = None
    HAS_PYAUDIO = False

from .applications import AudioApplication
from ..utils.logger import LoggerMixin


class ApplicationAudioRecorder(LoggerMixin):
    """Records audio from a specific application using Windows WASAPI"""
    
    def __init__(self, application: AudioApplication, sample_rate: int = 44100, channels: int = 2):
        """Initialize application audio recorder"""
        self.application = application
        self.requested_sample_rate = sample_rate
        self.actual_sample_rate = sample_rate  # Will be updated when we find the device
        self.channels = channels
        self.is_recording = False
        self.audio_data = []
        self.stream = None
        self.recording_thread = None
        self.level_callback = None
        
        # PyAudio instance
        self.pyaudio_instance = None
        
        if not HAS_PYAUDIO:
            self.logger.error("PyAudioWPatch not available - application-specific recording not supported")
            return
        
        try:
            self.pyaudio_instance = pyaudio.PyAudio()
        except Exception as e:
            self.logger.error(f"Failed to initialize PyAudio: {e}")
    
    def set_level_callback(self, callback: Callable):
        """Set callback for audio level updates"""
        self.level_callback = callback
    
    def start_recording(self) -> bool:
        """Start recording from the application"""
        if not self.pyaudio_instance:
            self.logger.error("PyAudio not initialized")
            return False
        
        if self.is_recording:
            self.logger.warning("Already recording")
            return True
        
        try:
            # Find the application's audio endpoint
            device_info = self._find_application_audio_device()
            if not device_info:
                self.logger.warning(f"Could not find audio device for application: {self.application.name}")
                # Fallback to system loopback
                return self._start_system_loopback_recording()
            
            # Update actual sample rate
            self.actual_sample_rate = device_info['sample_rate']
            
            self.logger.info(f"Using device sample rate: {self.actual_sample_rate}Hz (requested: {self.requested_sample_rate}Hz)")
            
            # Open audio stream for the specific application
            self.stream = self.pyaudio_instance.open(
                format=pyaudio.paFloat32,
                channels=self.channels,
                rate=device_info['sample_rate'],
                input=True,
                input_device_index=device_info['index'],
                frames_per_buffer=1024,
                stream_callback=self._audio_callback
            )
            
            self.stream.start_stream()
            self.is_recording = True
            self.audio_data = []
            
            self.logger.info(f"Started recording from application: {self.application.name} at {device_info['sample_rate']}Hz")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to start application recording: {e}")
            # Fallback to system loopback
            return self._start_system_loopback_recording()
    
    def _find_application_audio_device(self) -> Optional[dict]:
        """Find the audio device/endpoint for the specific application"""
        try:
            # Get all WASAPI loopback devices
            device_count = self.pyaudio_instance.get_device_count()
            
            for i in range(device_count):
                try:
                    device_info = self.pyaudio_instance.get_device_info_by_index(i)
                    
                    # Check if this is a WASAPI loopback device
                    if (device_info.get('maxInputChannels', 0) > 0 and 
                        'loopback' in device_info.get('name', '').lower()):
                        
                        # Get the device's default sample rate
                        device_sample_rate = int(device_info.get('defaultSampleRate', 44100))
                        
                        # For now, we'll use the first available loopback device
                        # In a more advanced implementation, we would use Windows Audio Session API
                        # to find the specific application's audio session
                        return {
                            'index': i,
                            'name': device_info['name'],
                            'info': device_info,
                            'sample_rate': device_sample_rate
                        }
                        
                except Exception as e:
                    self.logger.debug(f"Error checking device {i}: {e}")
                    continue
            
            return None
            
        except Exception as e:
            self.logger.error(f"Error finding application audio device: {e}")
            return None
    
    def _start_system_loopback_recording(self) -> bool:
        """Fallback to system loopback recording"""
        try:
            # Find any available loopback device
            device_count = self.pyaudio_instance.get_device_count()
            loopback_device = None
            device_sample_rate = self.requested_sample_rate
            
            for i in range(device_count):
                try:
                    device_info = self.pyaudio_instance.get_device_info_by_index(i)
                    if (device_info.get('maxInputChannels', 0) > 0 and 
                        'loopback' in device_info.get('name', '').lower()):
                        loopback_device = i
                        device_sample_rate = int(device_info.get('defaultSampleRate', 44100))
                        break
                except:
                    continue
            
            if loopback_device is None:
                self.logger.error("No loopback devices found")
                return False
            
            # Update actual sample rate
            self.actual_sample_rate = device_sample_rate
            
            self.logger.info(f"Fallback using sample rate: {self.actual_sample_rate}Hz (requested: {self.requested_sample_rate}Hz)")
            
            self.stream = self.pyaudio_instance.open(
                format=pyaudio.paFloat32,
                channels=self.channels,
                rate=device_sample_rate,
                input=True,
                input_device_index=loopback_device,
                frames_per_buffer=1024,
                stream_callback=self._audio_callback
            )
            
            self.stream.start_stream()
            self.is_recording = True
            self.audio_data = []
            
            self.logger.info(f"Started system loopback recording for application: {self.application.name} at {device_sample_rate}Hz")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to start system loopback recording: {e}")
            return False
    
    def _audio_callback(self, in_data, frame_count, time_info, status):
        """Audio stream callback"""
        if status:
            self.logger.debug(f"Audio callback status: {status}")
        
        # Convert bytes to numpy array
        audio_array = np.frombuffer(in_data, dtype=np.float32)
        
        # Store audio data
        self.audio_data.append(audio_array.copy())
        
        # Calculate audio level for callback
        if self.level_callback and len(audio_array) > 0:
            try:
                # Calculate RMS level
                rms = np.sqrt(np.mean(audio_array ** 2))
                # Convert to dB (with floor to avoid log(0))
                db_level = 20 * np.log10(max(rms, 1e-10))
                # Normalize to 0-1 range (assuming -60dB to 0dB range)
                normalized_level = max(0, min(1, (db_level + 60) / 60))
                
                # Call the level callback
                self.level_callback(normalized_level)
            except Exception as e:
                self.logger.debug(f"Error calculating audio level: {e}")
        
        return (None, pyaudio.paContinue)
    
    def stop_recording(self) -> bool:
        """Stop recording"""
        if not self.is_recording:
            return True
        
        try:
            self.is_recording = False
            
            if self.stream:
                self.stream.stop_stream()
                self.stream.close()
                self.stream = None
            
            self.logger.info(f"Stopped recording from application: {self.application.name}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error stopping application recording: {e}")
            return False
    
    def get_audio_data(self) -> Optional[np.ndarray]:
        """Get recorded audio data"""
        if not self.audio_data:
            return None
        
        try:
            # Concatenate all audio chunks
            combined_audio = np.concatenate(self.audio_data)
            
            # Reshape for stereo if needed
            if self.channels == 2 and len(combined_audio.shape) == 1:
                # Convert mono to stereo by duplicating the channel
                combined_audio = np.column_stack((combined_audio, combined_audio))
            
            return combined_audio
            
        except Exception as e:
            self.logger.error(f"Error processing audio data: {e}")
            return None
    
    def save_to_file(self, file_path: Path) -> bool:
        """Save recorded audio to file"""
        audio_data = self.get_audio_data()
        if audio_data is None:
            return False
        
        try:
            # Convert float32 to int16 for WAV file
            audio_int16 = (audio_data * 32767).astype(np.int16)
            
            with wave.open(str(file_path), 'wb') as wav_file:
                wav_file.setnchannels(self.channels)
                wav_file.setsampwidth(2)  # 16-bit
                wav_file.setframerate(self.actual_sample_rate)
                wav_file.writeframes(audio_int16.tobytes())
            
            self.logger.info(f"Saved application audio to: {file_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error saving application audio: {e}")
            return False
    
    def __del__(self):
        """Cleanup"""
        if self.is_recording:
            self.stop_recording()
        
        if self.pyaudio_instance:
            try:
                self.pyaudio_instance.terminate()
            except:
                pass
