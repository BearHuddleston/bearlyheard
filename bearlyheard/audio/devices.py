"""Audio device management for BearlyHeard"""

import platform
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass

try:
    import sounddevice as sd
except (ImportError, OSError) as e:
    sd = None

try:
    import pyaudiowpatch as pyaudio
except ImportError:
    pyaudio = None

from ..utils.logger import LoggerMixin


@dataclass
class AudioDevice:
    """Audio device information"""
    index: int
    name: str
    channels: int
    sample_rate: float
    is_input: bool
    is_output: bool
    is_default: bool = False
    is_loopback: bool = False


class AudioDeviceManager(LoggerMixin):
    """Manages audio device enumeration and selection"""
    
    def __init__(self):
        """Initialize audio device manager"""
        self._pyaudio_instance = None
        self._devices_cache = {}
        self._cache_valid = False
        
        # Check available backends
        self.has_sounddevice = sd is not None
        self.has_pyaudiowpatch = pyaudio is not None
        self.platform = platform.system()
        
        self.logger.info(f"Audio backends available: sounddevice={self.has_sounddevice}, "
                        f"pyaudiowpatch={self.has_pyaudiowpatch}, platform={self.platform}")
    
    def _get_pyaudio_instance(self):
        """Get PyAudio instance (lazy initialization)"""
        if not self.has_pyaudiowpatch:
            return None
            
        if self._pyaudio_instance is None:
            try:
                self._pyaudio_instance = pyaudio.PyAudio()
            except Exception as e:
                self.logger.error(f"Failed to initialize PyAudio: {e}")
                return None
        
        return self._pyaudio_instance
    
    def refresh_devices(self) -> None:
        """Refresh device cache"""
        self._devices_cache.clear()
        self._cache_valid = False
        self.logger.debug("Audio device cache cleared")
    
    def get_input_devices(self) -> List[AudioDevice]:
        """Get list of available input devices"""
        if not self._cache_valid:
            self._enumerate_devices()
        
        return [device for device in self._devices_cache.values() if device.is_input]
    
    def get_output_devices(self) -> List[AudioDevice]:
        """Get list of available output devices"""
        if not self._cache_valid:
            self._enumerate_devices()
        
        return [device for device in self._devices_cache.values() if device.is_output]
    
    def get_loopback_devices(self) -> List[AudioDevice]:
        """Get list of available loopback devices (Windows only)"""
        if self.platform != "Windows" or not self.has_pyaudiowpatch:
            return []
        
        if not self._cache_valid:
            self._enumerate_devices()
        
        return [device for device in self._devices_cache.values() if device.is_loopback]
    
    def get_default_input_device(self) -> Optional[AudioDevice]:
        """Get default input device"""
        devices = self.get_input_devices()
        for device in devices:
            if device.is_default:
                return device
        
        # Fallback to first available input device
        return devices[0] if devices else None
    
    def get_default_output_device(self) -> Optional[AudioDevice]:
        """Get default output device"""
        devices = self.get_output_devices()
        for device in devices:
            if device.is_default:
                return device
        
        # Fallback to first available output device
        return devices[0] if devices else None
    
    def get_device_by_name(self, name: str) -> Optional[AudioDevice]:
        """Get device by name"""
        if not self._cache_valid:
            self._enumerate_devices()
        
        for device in self._devices_cache.values():
            if device.name == name:
                return device
        
        return None
    
    def get_device_by_index(self, index: int) -> Optional[AudioDevice]:
        """Get device by index"""
        if not self._cache_valid:
            self._enumerate_devices()
        
        return self._devices_cache.get(index)
    
    def _enumerate_devices(self) -> None:
        """Enumerate all available audio devices"""
        self._devices_cache.clear()
        
        # Enumerate using sounddevice
        if self.has_sounddevice:
            self._enumerate_sounddevice()
        
        # Enumerate using PyAudioWPatch (for Windows loopback)
        if self.has_pyaudiowpatch and self.platform == "Windows":
            self._enumerate_pyaudiowpatch()
        
        self._cache_valid = True
        self.logger.info(f"Enumerated {len(self._devices_cache)} audio devices")
    
    def _enumerate_sounddevice(self) -> None:
        """Enumerate devices using sounddevice"""
        try:
            devices = sd.query_devices()
            default_input = sd.default.device[0] if sd.default.device[0] is not None else -1
            default_output = sd.default.device[1] if sd.default.device[1] is not None else -1
            
            for i, device_info in enumerate(devices):
                # Skip devices with no channels
                if device_info['max_input_channels'] == 0 and device_info['max_output_channels'] == 0:
                    continue
                
                device = AudioDevice(
                    index=i,
                    name=device_info['name'].strip(),
                    channels=max(device_info['max_input_channels'], device_info['max_output_channels']),
                    sample_rate=device_info['default_samplerate'],
                    is_input=device_info['max_input_channels'] > 0,
                    is_output=device_info['max_output_channels'] > 0,
                    is_default=(i == default_input or i == default_output)
                )
                
                self._devices_cache[i] = device
                
        except Exception as e:
            self.logger.error(f"Failed to enumerate sounddevice devices: {e}")
    
    def _enumerate_pyaudiowpatch(self) -> None:
        """Enumerate devices using PyAudioWPatch (Windows loopback support)"""
        pa = self._get_pyaudio_instance()
        if not pa:
            return
        
        try:
            device_count = pa.get_device_count()
            
            for i in range(device_count):
                try:
                    device_info = pa.get_device_info_by_index(i)
                    
                    # Check if this is a loopback device
                    is_loopback = False
                    if self.platform == "Windows":
                        # PyAudioWPatch specific check for loopback devices
                        try:
                            # Test if device supports loopback
                            is_loopback = (
                                device_info.get('isLoopbackDevice', False) or
                                'loopback' in device_info['name'].lower() or
                                device_info.get('hostApi') == pa.get_host_api_info_by_type(pyaudio.paWASAPI)['index']
                            )
                        except:
                            pass
                    
                    # Create device entry (offset index to avoid conflicts with sounddevice)
                    device_index = 1000 + i  # Offset to avoid conflicts
                    
                    device = AudioDevice(
                        index=device_index,
                        name=device_info['name'].strip(),
                        channels=max(device_info['maxInputChannels'], device_info['maxOutputChannels']),
                        sample_rate=device_info['defaultSampleRate'],
                        is_input=device_info['maxInputChannels'] > 0,
                        is_output=device_info['maxOutputChannels'] > 0,
                        is_loopback=is_loopback
                    )
                    
                    # Only add loopback devices or devices not already in cache
                    if is_loopback or device.name not in [d.name for d in self._devices_cache.values()]:
                        self._devices_cache[device_index] = device
                
                except Exception as e:
                    self.logger.debug(f"Skipping PyAudio device {i}: {e}")
                    continue
                    
        except Exception as e:
            self.logger.error(f"Failed to enumerate PyAudioWPatch devices: {e}")
    
    def test_device(self, device: AudioDevice, duration: float = 1.0) -> bool:
        """
        Test if a device is working
        
        Args:
            device: Device to test
            duration: Test duration in seconds
            
        Returns:
            True if device is working
        """
        if not self.has_sounddevice:
            return False
        
        try:
            if device.is_input:
                # Test recording
                recording = sd.rec(
                    frames=int(duration * device.sample_rate),
                    samplerate=device.sample_rate,
                    channels=min(device.channels, 2),
                    device=device.index if device.index < 1000 else None
                )
                sd.wait()
                return recording is not None and len(recording) > 0
            
            elif device.is_output:
                # Test playback with silence
                silence = sd.zeros((int(duration * device.sample_rate), min(device.channels, 2)))
                sd.play(silence, samplerate=device.sample_rate, device=device.index if device.index < 1000 else None)
                sd.wait()
                return True
                
        except Exception as e:
            self.logger.debug(f"Device test failed for {device.name}: {e}")
            return False
        
        return False
    
    def get_device_capabilities(self, device: AudioDevice) -> Dict[str, List]:
        """Get supported sample rates and formats for a device"""
        capabilities = {
            "sample_rates": [],
            "formats": []
        }
        
        if not self.has_sounddevice or device.index >= 1000:
            return capabilities
        
        # Test common sample rates
        test_rates = [8000, 11025, 16000, 22050, 44100, 48000, 88200, 96000]
        
        for rate in test_rates:
            try:
                if device.is_input:
                    sd.check_input_settings(device=device.index, samplerate=rate)
                    capabilities["sample_rates"].append(rate)
                elif device.is_output:
                    sd.check_output_settings(device=device.index, samplerate=rate)
                    capabilities["sample_rates"].append(rate)
            except:
                continue
        
        return capabilities
    
    def __del__(self):
        """Cleanup PyAudio instance"""
        if self._pyaudio_instance:
            try:
                self._pyaudio_instance.terminate()
            except:
                pass