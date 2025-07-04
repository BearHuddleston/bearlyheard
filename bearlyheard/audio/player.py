"""Audio playback implementation for BearlyHeard"""

from pathlib import Path
from typing import Optional, Callable
import threading
import time

try:
    import sounddevice as sd
    import numpy as np
    from scipy.io import wavfile
    HAS_AUDIO_LIBS = True
except (ImportError, OSError):
    sd = None
    np = None
    wavfile = None
    HAS_AUDIO_LIBS = False

from PyQt6.QtCore import QObject, pyqtSignal
from ..utils.logger import LoggerMixin


class AudioPlayer(QObject, LoggerMixin):
    """Simple audio player for recordings"""
    
    # Qt signals for thread-safe communication
    progress_updated = pyqtSignal(float, float)  # position, duration
    playback_finished = pyqtSignal()
    
    def __init__(self):
        """Initialize audio player"""
        super().__init__()
        self.is_playing = False
        self.audio_data = None
        self.sample_rate = 44100
        self.current_position = 0
        self.duration = 0.0
        self.play_thread = None
        self.progress_callback = None
        
        if not HAS_AUDIO_LIBS:
            self.logger.warning("Audio libraries not available, playback disabled")
    
    def load_file(self, file_path: Path) -> bool:
        """
        Load audio file for playback
        
        Args:
            file_path: Path to audio file
            
        Returns:
            True if file loaded successfully
        """
        if not HAS_AUDIO_LIBS:
            self.logger.error("Cannot load file: audio libraries not available")
            return False
        
        if not file_path.exists():
            self.logger.error(f"Audio file not found: {file_path}")
            return False
        
        try:
            # Load WAV file
            self.sample_rate, self.audio_data = wavfile.read(str(file_path))
            
            # Convert to float if needed
            if self.audio_data.dtype == np.int16:
                self.audio_data = self.audio_data.astype(np.float32) / 32768.0
            elif self.audio_data.dtype == np.int32:
                self.audio_data = self.audio_data.astype(np.float32) / 2147483648.0
            
            # Calculate duration
            self.duration = len(self.audio_data) / self.sample_rate
            self.current_position = 0
            
            self.logger.info(f"Loaded audio file: {file_path} ({self.duration:.2f}s)")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to load audio file {file_path}: {e}")
            return False
    
    def play(self, start_position: float = 0.0) -> bool:
        """
        Start playback
        
        Args:
            start_position: Start position in seconds
            
        Returns:
            True if playback started successfully
        """
        if not HAS_AUDIO_LIBS or self.audio_data is None:
            self.logger.error("Cannot play: no audio data loaded")
            return False
        
        if self.is_playing:
            self.logger.warning("Already playing")
            return False
        
        try:
            self.current_position = max(0, min(start_position, self.duration))
            self.is_playing = True
            
            # Start playback in separate thread
            self.play_thread = threading.Thread(target=self._play_worker)
            self.play_thread.daemon = True
            self.play_thread.start()
            
            self.logger.info(f"Started playback from {start_position:.2f}s")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to start playback: {e}")
            self.is_playing = False
            return False
    
    def stop(self) -> bool:
        """
        Stop playback
        
        Returns:
            True if playback stopped successfully
        """
        if not self.is_playing:
            return True
        
        try:
            self.is_playing = False
            
            # Wait for playback thread to finish
            if self.play_thread and self.play_thread.is_alive():
                self.play_thread.join(timeout=1.0)
            
            self.logger.info("Stopped playback")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to stop playback: {e}")
            return False
    
    def pause(self) -> bool:
        """
        Pause playback
        
        Returns:
            True if playback paused successfully
        """
        if self.is_playing:
            self.is_playing = False
            self.logger.info(f"Paused playback at {self.current_position:.2f}s")
            return True
        return False
    
    def resume(self) -> bool:
        """
        Resume playback from current position
        
        Returns:
            True if playback resumed successfully
        """
        if not self.is_playing and self.audio_data is not None:
            return self.play(self.current_position)
        return False
    
    def seek(self, position: float) -> bool:
        """
        Seek to specific position
        
        Args:
            position: Position in seconds
            
        Returns:
            True if seek successful
        """
        if self.audio_data is None:
            return False
        
        was_playing = self.is_playing
        
        if was_playing:
            self.stop()
        
        self.current_position = max(0, min(position, self.duration))
        
        if was_playing:
            return self.play(self.current_position)
        
        return True
    
    def get_position(self) -> float:
        """Get current playback position in seconds"""
        return self.current_position
    
    def get_duration(self) -> float:
        """Get total duration in seconds"""
        return self.duration
    
    def set_progress_callback(self, callback: Callable[[float, float], None]):
        """Set callback for progress updates (position, duration)"""
        self.progress_callback = callback
    
    def _play_worker(self):
        """Worker thread for audio playback"""
        try:
            # Calculate start frame
            start_frame = int(self.current_position * self.sample_rate)
            
            # Get audio data to play
            if len(self.audio_data.shape) == 1:
                # Mono
                audio_to_play = self.audio_data[start_frame:]
                channels = 1
            else:
                # Stereo or multi-channel
                audio_to_play = self.audio_data[start_frame:, :]
                channels = audio_to_play.shape[1]
            
            if len(audio_to_play) == 0:
                self.is_playing = False
                return
            
            # Set up playback state
            self.playback_data = audio_to_play
            self.playback_index = 0
            
            # Play audio using sounddevice
            with sd.OutputStream(
                samplerate=self.sample_rate,
                channels=channels,
                callback=self._audio_callback,
                blocksize=1024
            ) as stream:
                
                # Keep playing until finished or stopped
                while self.is_playing and self.playback_index < len(self.playback_data):
                    # Update position
                    self.current_position = (start_frame + self.playback_index) / self.sample_rate
                    
                    # Emit progress signal
                    self.progress_updated.emit(self.current_position, self.duration)
                    
                    # Small delay
                    time.sleep(0.1)
            
            self.is_playing = False
            self.playback_finished.emit()
            
        except Exception as e:
            self.logger.error(f"Playback error: {e}")
            self.is_playing = False
    
    def _audio_callback(self, outdata, frames, time, status):
        """Audio stream callback for playback"""
        if status:
            self.logger.warning(f"Playback callback status: {status}")
        
        if not self.is_playing or not hasattr(self, 'playback_data'):
            outdata.fill(0)
            return
        
        # Get the next chunk of audio data
        start_idx = self.playback_index
        end_idx = min(start_idx + frames, len(self.playback_data))
        
        if start_idx >= len(self.playback_data):
            # End of audio
            outdata.fill(0)
            self.is_playing = False
            return
        
        # Copy audio data to output
        chunk_size = end_idx - start_idx
        if len(self.playback_data.shape) == 1:
            # Mono
            outdata[:chunk_size, 0] = self.playback_data[start_idx:end_idx]
            if outdata.shape[1] > 1:  # If output is stereo, duplicate to both channels
                outdata[:chunk_size, 1] = self.playback_data[start_idx:end_idx]
        else:
            # Multi-channel
            outdata[:chunk_size, :] = self.playback_data[start_idx:end_idx, :]
        
        # Fill remaining with silence if needed
        if chunk_size < frames:
            outdata[chunk_size:, :] = 0
        
        # Update playback index
        self.playback_index = end_idx