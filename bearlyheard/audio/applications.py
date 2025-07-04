"""Application detection and audio source management for BearlyHeard"""

import platform
import subprocess
import json
from typing import List, Dict, Optional, Set
from dataclasses import dataclass
from pathlib import Path

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    psutil = None
    HAS_PSUTIL = False

from ..utils.logger import LoggerMixin


@dataclass
class AudioApplication:
    """Information about an application with audio capabilities"""
    name: str
    process_name: str
    pid: int
    executable_path: str
    is_playing_audio: bool = False
    audio_session_id: Optional[str] = None
    icon_path: Optional[str] = None
    window_title: Optional[str] = None
    command_line: Optional[str] = None


class ApplicationManager(LoggerMixin):
    """Manages detection and monitoring of applications with audio capabilities"""
    
    def __init__(self):
        """Initialize application manager"""
        self.platform = platform.system()
        self.has_psutil = HAS_PSUTIL
        self._applications_cache = {}
        self._cache_valid = False
        
        # Known audio applications (common ones)
        self.known_audio_apps = {
            'chrome.exe': 'Google Chrome',
            'firefox.exe': 'Mozilla Firefox',
            'msedge.exe': 'Microsoft Edge',
            'brave.exe': 'Brave Browser',
            'opera.exe': 'Opera',
            'spotify.exe': 'Spotify',
            'discord.exe': 'Discord',
            'teams.exe': 'Microsoft Teams',
            'ms-teams.exe': 'Microsoft Teams',
            'zoom.exe': 'Zoom',
            'skype.exe': 'Skype',
            'slack.exe': 'Slack',
            'vlc.exe': 'VLC Media Player',
            'wmplayer.exe': 'Windows Media Player',
            'itunes.exe': 'iTunes',
            'steam.exe': 'Steam',
            'obs64.exe': 'OBS Studio',
            'obs32.exe': 'OBS Studio',
            'audacity.exe': 'Audacity',
            'foobar2000.exe': 'foobar2000',
            'winamp.exe': 'Winamp',
            'musicbee.exe': 'MusicBee',
            'potplayer.exe': 'PotPlayer',
            'mpc-hc64.exe': 'Media Player Classic',
            'mpc-hc.exe': 'Media Player Classic',
            'notepad.exe': 'Notepad',  # For testing
            'calculator.exe': 'Calculator',  # For testing
            'whatsapp.exe': 'WhatsApp',
            'telegram.exe': 'Telegram',
            'youtube.exe': 'YouTube Music',
            'amazonmusic.exe': 'Amazon Music',
            'applemusic.exe': 'Apple Music',
        }
        
        self.logger.info(f"Application manager initialized for {self.platform}")
    
    def refresh_applications(self) -> None:
        """Refresh applications cache"""
        self._applications_cache.clear()
        self._cache_valid = False
        self.logger.debug("Applications cache cleared")
    
    def get_audio_applications(self) -> List[AudioApplication]:
        """Get list of running applications that can produce audio"""
        if not self._cache_valid:
            self._detect_applications()
        
        return list(self._applications_cache.values())
    
    def get_application_by_name(self, name: str) -> Optional[AudioApplication]:
        """Get application by name"""
        if not self._cache_valid:
            self._detect_applications()
        
        for app in self._applications_cache.values():
            if app.name == name:
                return app
        
        return None
    
    def get_application_by_pid(self, pid: int) -> Optional[AudioApplication]:
        """Get application by process ID"""
        if not self._cache_valid:
            self._detect_applications()
        
        return self._applications_cache.get(pid)
    
    def _detect_applications(self) -> None:
        """Detect running applications with audio capabilities"""
        self._applications_cache.clear()
        
        if self.platform == "Windows":
            self._detect_windows_applications()
        elif self.platform == "Darwin":  # macOS
            self._detect_macos_applications()
        elif self.platform == "Linux":
            self._detect_linux_applications()
        
        self._cache_valid = True
        self.logger.debug(f"Detected {len(self._applications_cache)} audio applications")
    
    def _detect_windows_applications(self) -> None:
        """Detect Windows applications with audio capabilities"""
        if not self.has_psutil:
            self.logger.warning("psutil not available, using basic process detection")
            self._detect_basic_processes()
            return
        
        seen_apps = set()  # Track applications we've already added
        
        try:
            # Get all running processes
            for proc in psutil.process_iter(['pid', 'name', 'exe', 'cmdline']):
                try:
                    proc_info = proc.info
                    if not proc_info['name']:
                        continue
                    
                    process_name = proc_info['name'].lower()
                    
                    # Check if it's a known audio application
                    if process_name in self.known_audio_apps:
                        app_name = self.known_audio_apps[process_name]
                        
                        # Skip if we've already added this application
                        if app_name in seen_apps:
                            continue
                        
                        seen_apps.add(app_name)
                        
                        # Try to get executable path
                        exe_path = proc_info.get('exe', '')
                        if not exe_path and proc_info.get('cmdline'):
                            exe_path = proc_info['cmdline'][0] if proc_info['cmdline'] else ''
                        
                        app = AudioApplication(
                            name=app_name,
                            process_name=process_name,
                            pid=proc_info['pid'],
                            executable_path=exe_path or '',
                            is_playing_audio=self._check_audio_activity(proc_info['pid']),
                            window_title=None,
                            command_line=' '.join(proc_info.get('cmdline', [])) if proc_info.get('cmdline') else None
                        )
                        
                        self._applications_cache[proc_info['pid']] = app
                        
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    continue
                except Exception as e:
                    self.logger.debug(f"Error processing process: {e}")
                    continue
        
        except Exception as e:
            self.logger.error(f"Error detecting Windows applications: {e}")
            self._detect_basic_processes()
    
    def _detect_macos_applications(self) -> None:
        """Detect macOS applications with audio capabilities"""
        # For now, use basic process detection
        # TODO: Implement proper macOS audio session detection
        self._detect_basic_processes()
    
    def _detect_linux_applications(self) -> None:
        """Detect Linux applications with audio capabilities"""
        # For now, use basic process detection
        # TODO: Implement proper PulseAudio/ALSA detection
        self._detect_basic_processes()
    
    def _detect_basic_processes(self) -> None:
        """Basic process detection fallback"""
        seen_apps = set()  # Track applications we've already added
        
        try:
            if self.platform == "Windows":
                # Use tasklist command
                result = subprocess.run(
                    ['tasklist', '/fo', 'csv'],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                
                if result.returncode == 0:
                    lines = result.stdout.strip().split('\n')
                    if len(lines) > 1:  # Skip header
                        for line in lines[1:]:
                            try:
                                # Parse CSV line
                                parts = [part.strip('"') for part in line.split('","')]
                                if len(parts) >= 2:
                                    process_name = parts[0].lower()
                                    pid = int(parts[1])
                                    
                                    if process_name in self.known_audio_apps:
                                        app_name = self.known_audio_apps[process_name]
                                        
                                        # Skip if we've already added this application
                                        if app_name in seen_apps:
                                            continue
                                        
                                        seen_apps.add(app_name)
                                        
                                        app = AudioApplication(
                                            name=app_name,
                                            process_name=process_name,
                                            pid=pid,
                                            executable_path='',
                                            is_playing_audio=False,
                                            window_title=None,
                                            command_line=None
                                        )
                                        
                                        self._applications_cache[pid] = app
                            except (ValueError, IndexError) as e:
                                self.logger.debug(f"Error parsing tasklist line: {e}")
                                continue
            
            else:
                # Use ps command for Unix-like systems
                result = subprocess.run(
                    ['ps', 'aux'],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                
                if result.returncode == 0:
                    lines = result.stdout.strip().split('\n')
                    for line in lines[1:]:  # Skip header
                        try:
                            parts = line.split()
                            if len(parts) >= 11:
                                pid = int(parts[1])
                                command = ' '.join(parts[10:])
                                process_name = Path(parts[10]).name.lower()
                                
                                if process_name in self.known_audio_apps:
                                    app_name = self.known_audio_apps[process_name]
                                    
                                    # Skip if we've already added this application
                                    if app_name in seen_apps:
                                        continue
                                    
                                    seen_apps.add(app_name)
                                    
                                    app = AudioApplication(
                                        name=app_name,
                                        process_name=process_name,
                                        pid=pid,
                                        executable_path=parts[10],
                                        is_playing_audio=False,
                                        window_title=None,
                                        command_line=command
                                    )
                                    
                                    self._applications_cache[pid] = app
                        except (ValueError, IndexError) as e:
                            self.logger.debug(f"Error parsing ps line: {e}")
                            continue
        
        except subprocess.TimeoutExpired:
            self.logger.warning("Process detection timed out")
        except Exception as e:
            self.logger.error(f"Error in basic process detection: {e}")
    
    def _check_audio_activity(self, pid: int) -> bool:
        """Check if a process is currently playing audio (Windows only)"""
        if self.platform != "Windows":
            return False
        
        try:
            # This is a simplified check - in a real implementation,
            # you would use Windows Audio Session API (WASAPI) to check
            # if the process has active audio sessions
            
            # For now, we'll assume processes are potentially playing audio
            # if they're known audio applications
            return True
            
        except Exception as e:
            self.logger.debug(f"Error checking audio activity for PID {pid}: {e}")
            return False
    
    def get_audio_sessions(self) -> List[Dict]:
        """Get active audio sessions (Windows only)"""
        if self.platform != "Windows":
            return []
        
        # TODO: Implement Windows Audio Session API integration
        # This would require additional Windows-specific libraries
        # like pycaw or direct Windows API calls
        
        return []
    
    def monitor_audio_activity(self, callback) -> None:
        """Monitor audio activity changes (future implementation)"""
        # TODO: Implement real-time audio activity monitoring
        pass
