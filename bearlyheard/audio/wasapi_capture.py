"""Windows Audio Session API (WASAPI) implementation for application-specific audio capture"""

import platform
import threading
import time
import wave
import numpy as np
from typing import Optional, Callable, List, Dict, Any
from pathlib import Path

# Windows-specific imports
if platform.system() == "Windows":
    try:
        from pycaw.pycaw import AudioUtilities
        HAS_WASAPI = True
    except ImportError as e:
        print(f"WASAPI imports failed: {e}")
        HAS_WASAPI = False
else:
    HAS_WASAPI = False

from .applications import AudioApplication
from ..utils.logger import LoggerMixin


class WASAPIApplicationRecorder(LoggerMixin):
    """Records audio from a specific application using Windows Audio Session API"""
    
    def __init__(self, application: AudioApplication, sample_rate: int = 44100, channels: int = 2):
        """Initialize WASAPI application recorder"""
        self.application = application
        self.requested_sample_rate = sample_rate  # What we want
        self.actual_sample_rate = sample_rate     # What we actually get
        self.channels = channels
        self.is_recording = False
        self.audio_data = []
        self.recording_thread = None
        self.level_callback = None
        self._stop_event = threading.Event()
        
        # WASAPI components
        self.audio_session = None
        self.audio_client = None
        self.capture_client = None
        
        if not HAS_WASAPI:
            self.logger.error("WASAPI not available - application-specific recording not supported")
            return
        
        if platform.system() != "Windows":
            self.logger.error("WASAPI only supported on Windows")
            return
        
        self.logger.info(f"Initialized WASAPI recorder for application: {application.name}")
    
    def set_level_callback(self, callback: Callable):
        """Set callback for audio level updates"""
        self.level_callback = callback
    
    def _find_application_audio_session(self) -> Optional[Any]:
        """Find the audio session for the specific application"""
        try:
            # Get all audio sessions
            sessions = AudioUtilities.GetAllSessions()
            
            for session in sessions:
                if session.Process and session.Process.pid == self.application.pid:
                    self.logger.info(f"Found audio session for {self.application.name} (PID: {self.application.pid})")
                    return session
            
            # Fallback: try to match by process name
            for session in sessions:
                if session.Process and session.Process.name().lower() == self.application.process_name:
                    self.logger.info(f"Found audio session for {self.application.name} by process name")
                    return session
            
            self.logger.warning(f"No audio session found for application: {self.application.name}")
            return None
            
        except Exception as e:
            self.logger.error(f"Error finding application audio session: {e}")
            return None
    
    def _get_application_audio_endpoint(self) -> Optional[Any]:
        """Get the audio endpoint device for the application"""
        try:
            # Find the application's audio session
            session = self._find_application_audio_session()
            if not session:
                return None
            
            # Get the audio endpoint device
            # For now, we'll use the default playback device and capture its loopback
            devices = AudioUtilities.GetSpeakers()
            if devices:
                self.logger.info(f"Using default playback device for loopback capture")
                return devices
            
            return None
            
        except Exception as e:
            self.logger.error(f"Error getting application audio endpoint: {e}")
            return None
    
    def start_recording(self) -> bool:
        """Start recording from the application using WASAPI"""
        if not HAS_WASAPI:
            self.logger.error("WASAPI not available")
            return False
        
        if self.is_recording:
            self.logger.warning("Already recording")
            return True
        
        try:
            # Find application's audio session
            self.audio_session = self._find_application_audio_session()
            if not self.audio_session:
                self.logger.warning(f"Could not find audio session for {self.application.name}")
                return self._fallback_to_system_loopback()
            
            # Get the audio endpoint
            endpoint = self._get_application_audio_endpoint()
            if not endpoint:
                self.logger.warning("Could not get audio endpoint")
                return self._fallback_to_system_loopback()
            
            # Start recording thread
            self._stop_event.clear()
            self.recording_thread = threading.Thread(target=self._recording_loop, daemon=True)
            self.recording_thread.start()
            
            self.is_recording = True
            self.audio_data = []
            
            self.logger.info(f"Started WASAPI recording from application: {self.application.name}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to start WASAPI recording: {e}")
            return self._fallback_to_system_loopback()
    
    def _fallback_to_system_loopback(self) -> bool:
        """Fallback to system loopback recording"""
        try:
            # Import here to avoid circular imports
            from .app_recorder import ApplicationAudioRecorder
            
            self.logger.info("Falling back to system loopback recording")
            
            # Create fallback recorder
            self.fallback_recorder = ApplicationAudioRecorder(self.application, self.requested_sample_rate, self.channels)
            if self.level_callback:
                self.fallback_recorder.set_level_callback(self.level_callback)
            
            return self.fallback_recorder.start_recording()
            
        except Exception as e:
            self.logger.error(f"Fallback recording failed: {e}")
            return False
    
    def _recording_loop(self):
        """Main recording loop using WASAPI"""
        try:
            import pyaudiowpatch as pyaudio
            
            # Initialize PyAudio for WASAPI
            pa = pyaudio.PyAudio()
            
            # Find loopback device (for now, we'll use system loopback)
            # TODO: Implement true application-specific capture
            loopback_device = None
            for i in range(pa.get_device_count()):
                device_info = pa.get_device_info_by_index(i)
                if (device_info.get('maxInputChannels', 0) > 0 and 
                    'loopback' in device_info.get('name', '').lower()):
                    loopback_device = i
                    break
            
            if loopback_device is None:
                self.logger.error("No loopback device found")
                return
            
            # Open audio stream
            device_info = pa.get_device_info_by_index(loopback_device)
            self.actual_sample_rate = int(device_info['defaultSampleRate'])
            
            self.logger.info(f"Device sample rate: {self.actual_sample_rate}Hz, Requested: {self.requested_sample_rate}Hz")
            
            stream = pa.open(
                format=pyaudio.paFloat32,
                channels=min(self.channels, device_info['maxInputChannels']),
                rate=self.actual_sample_rate,
                input=True,
                input_device_index=loopback_device,
                frames_per_buffer=1024
            )
            
            self.logger.info(f"WASAPI recording loop started with device: {device_info['name']} at {self.actual_sample_rate}Hz")
            
            # Recording loop
            while not self._stop_event.is_set():
                try:
                    # Read audio data
                    data = stream.read(1024, exception_on_overflow=False)
                    audio_array = np.frombuffer(data, dtype=np.float32)
                    
                    # Store audio data
                    self.audio_data.append(audio_array.copy())
                    
                    # Calculate and report audio level
                    if self.level_callback and len(audio_array) > 0:
                        rms = np.sqrt(np.mean(audio_array ** 2))
                        db_level = 20 * np.log10(max(rms, 1e-10))
                        normalized_level = max(0, min(1, (db_level + 60) / 60))
                        self.level_callback(normalized_level)
                    
                except Exception as e:
                    if not self._stop_event.is_set():
                        self.logger.debug(f"Error in recording loop: {e}")
                    break
            
            # Cleanup
            stream.stop_stream()
            stream.close()
            pa.terminate()
            
        except Exception as e:
            self.logger.error(f"Error in WASAPI recording loop: {e}")
    
    def stop_recording(self) -> bool:
        """Stop recording"""
        if not self.is_recording:
            return True
        
        try:
            self.is_recording = False
            self._stop_event.set()
            
            # Wait for recording thread to finish
            if self.recording_thread and self.recording_thread.is_alive():
                self.recording_thread.join(timeout=2.0)
            
            # Check if we used fallback recorder
            if hasattr(self, 'fallback_recorder'):
                return self.fallback_recorder.stop_recording()
            
            self.logger.info(f"Stopped WASAPI recording from application: {self.application.name}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error stopping WASAPI recording: {e}")
            return False
    
    def get_audio_data(self) -> Optional[np.ndarray]:
        """Get recorded audio data"""
        # Check if we used fallback recorder
        if hasattr(self, 'fallback_recorder'):
            return self.fallback_recorder.get_audio_data()
        
        if not self.audio_data:
            return None
        
        try:
            # Concatenate all audio chunks
            combined_audio = np.concatenate(self.audio_data)
            
            # Reshape for stereo if needed
            if self.channels == 2 and len(combined_audio.shape) == 1:
                combined_audio = np.column_stack((combined_audio, combined_audio))
            
            return combined_audio
            
        except Exception as e:
            self.logger.error(f"Error processing WASAPI audio data: {e}")
            return None
    
    def save_to_file(self, file_path: Path) -> bool:
        """Save recorded audio to file"""
        # Check if we used fallback recorder
        if hasattr(self, 'fallback_recorder'):
            return self.fallback_recorder.save_to_file(file_path)
        
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
            
            self.logger.info(f"Saved WASAPI audio to: {file_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error saving WASAPI audio: {e}")
            return False
    
    def get_application_volume(self) -> float:
        """Get the current volume level of the application"""
        try:
            if self.audio_session:
                volume = self.audio_session.SimpleAudioVolume
                if volume:
                    return volume.GetMasterVolume()
            return 1.0
        except Exception as e:
            self.logger.debug(f"Error getting application volume: {e}")
            return 1.0
    
    def set_application_volume(self, volume: float) -> bool:
        """Set the volume level of the application (0.0 to 1.0)"""
        try:
            if self.audio_session:
                volume_control = self.audio_session.SimpleAudioVolume
                if volume_control:
                    volume_control.SetMasterVolume(max(0.0, min(1.0, volume)), None)
                    return True
            return False
        except Exception as e:
            self.logger.error(f"Error setting application volume: {e}")
            return False
    
    def is_application_playing_audio(self) -> bool:
        """Check if the application is currently playing audio"""
        try:
            if self.audio_session:
                state = self.audio_session.State
                # AudioSessionStateActive = 1
                return state == 1
            return False
        except Exception as e:
            self.logger.debug(f"Error checking application audio state: {e}")
            return False
    
    def __del__(self):
        """Cleanup"""
        if self.is_recording:
            self.stop_recording()
