"""Configuration management for BearlyHeard"""

import json
from pathlib import Path
from typing import Any, Dict, Optional, Union
from dataclasses import dataclass, asdict

from .logger import LoggerMixin


@dataclass
class AudioConfig:
    """Audio recording configuration"""
    sample_rate: int = 44100
    channels: int = 2
    chunk_size: int = 1024
    format_bits: int = 16
    application_device: Optional[str] = None
    microphone_device: Optional[str] = None


@dataclass
class TranscriptionConfig:
    """Transcription configuration"""
    model_size: str = "base"  # tiny, base, small, medium, large
    language: Optional[str] = None  # Auto-detect if None
    task: str = "transcribe"  # transcribe or translate
    beam_size: int = 5
    best_of: int = 5
    temperature: float = 0.0


@dataclass
class SummarizationConfig:
    """Summarization configuration"""
    model_path: Optional[str] = None
    max_tokens: int = 1000
    temperature: float = 0.3
    context_length: int = 4096


@dataclass
class UIConfig:
    """UI configuration"""
    theme: str = "dark"  # dark or light
    window_width: int = 800
    window_height: int = 600
    auto_transcribe: bool = True
    show_audio_levels: bool = True


class Config(LoggerMixin):
    """Application configuration manager"""
    
    def __init__(self, config_dir: Optional[Path] = None):
        """
        Initialize configuration manager
        
        Args:
            config_dir: Custom config directory path
        """
        self.config_dir = config_dir or self._get_default_config_dir()
        self.config_file = self.config_dir / "config.json"
        
        # Configuration sections
        self.audio = AudioConfig()
        self.transcription = TranscriptionConfig()
        self.summarization = SummarizationConfig()
        self.ui = UIConfig()
        
        # Load existing configuration
        self.load()
    
    def _get_default_config_dir(self) -> Path:
        """Get default configuration directory"""
        if Path.home().name == "root":
            # Running as root
            config_dir = Path("/etc/bearlyheard")
        else:
            # User directory
            config_dir = Path.home() / ".config" / "bearlyheard"
        
        config_dir.mkdir(parents=True, exist_ok=True)
        return config_dir
    
    def load(self) -> None:
        """Load configuration from file"""
        if not self.config_file.exists():
            self.logger.info(f"Config file not found at {self.config_file}, using defaults")
            self.save()  # Create default config
            return
        
        try:
            with open(self.config_file, 'r') as f:
                data = json.load(f)
            
            # Update configuration sections
            if "audio" in data:
                self.audio = AudioConfig(**data["audio"])
            if "transcription" in data:
                self.transcription = TranscriptionConfig(**data["transcription"])
            if "summarization" in data:
                self.summarization = SummarizationConfig(**data["summarization"])
            if "ui" in data:
                self.ui = UIConfig(**data["ui"])
                
            self.logger.info(f"Configuration loaded from {self.config_file}")
            
        except Exception as e:
            self.logger.error(f"Failed to load configuration: {e}")
            self.logger.info("Using default configuration")
    
    def save(self) -> None:
        """Save configuration to file"""
        try:
            config_data = {
                "audio": asdict(self.audio),
                "transcription": asdict(self.transcription),
                "summarization": asdict(self.summarization),
                "ui": asdict(self.ui)
            }
            
            with open(self.config_file, 'w') as f:
                json.dump(config_data, f, indent=2)
            
            self.logger.info(f"Configuration saved to {self.config_file}")
            
        except Exception as e:
            self.logger.error(f"Failed to save configuration: {e}")
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value by dot notation (e.g., 'audio.sample_rate')"""
        try:
            section, setting = key.split('.', 1)
            config_section = getattr(self, section)
            return getattr(config_section, setting, default)
        except (ValueError, AttributeError):
            return default
    
    def set(self, key: str, value: Any) -> None:
        """Set configuration value by dot notation"""
        try:
            section, setting = key.split('.', 1)
            config_section = getattr(self, section)
            setattr(config_section, setting, value)
            self.save()
        except (ValueError, AttributeError) as e:
            self.logger.error(f"Failed to set config {key}={value}: {e}")
    
    def reset_section(self, section: str) -> None:
        """Reset a configuration section to defaults"""
        if section == "audio":
            self.audio = AudioConfig()
        elif section == "transcription":
            self.transcription = TranscriptionConfig()
        elif section == "summarization":
            self.summarization = SummarizationConfig()
        elif section == "ui":
            self.ui = UIConfig()
        else:
            raise ValueError(f"Unknown configuration section: {section}")
        
        self.save()
        self.logger.info(f"Reset {section} configuration to defaults")
    
    def get_data_dir(self) -> Path:
        """Get data directory for storing recordings, transcripts, etc."""
        data_dir = Path.home() / "Documents" / "BearlyHeard"
        data_dir.mkdir(parents=True, exist_ok=True)
        return data_dir
    
    def get_models_dir(self) -> Path:
        """Get models directory"""
        models_dir = Path(__file__).parent.parent.parent / "models"
        models_dir.mkdir(parents=True, exist_ok=True)
        return models_dir