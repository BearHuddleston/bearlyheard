"""File management utilities for BearlyHeard"""

import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict

from .logger import LoggerMixin


@dataclass
class RecordingMetadata:
    """Metadata for a recording"""
    recording_id: str
    timestamp: str
    duration: str = "00:00:00"
    file_size: int = 0
    participants: List[str] = None
    audio_sources: Dict[str, str] = None
    transcription: Optional[Dict[str, Any]] = None
    summary: Optional[Dict[str, Any]] = None
    
    def __post_init__(self):
        if self.participants is None:
            self.participants = []
        if self.audio_sources is None:
            self.audio_sources = {}


class FileManager(LoggerMixin):
    """Manages files and metadata for BearlyHeard"""
    
    def __init__(self, data_dir: Optional[Path] = None):
        """
        Initialize file manager
        
        Args:
            data_dir: Custom data directory path
        """
        self.data_dir = data_dir or self._get_default_data_dir()
        self._ensure_directories()
    
    def _get_default_data_dir(self) -> Path:
        """Get default data directory"""
        return Path.home() / "Documents" / "BearlyHeard"
    
    def _ensure_directories(self) -> None:
        """Ensure all required directories exist"""
        directories = [
            self.data_dir,
            self.data_dir / "recordings",
            self.data_dir / "transcripts", 
            self.data_dir / "summaries",
            self.data_dir / "exports",
            self.data_dir / "metadata"
        ]
        
        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)
        
        self.logger.info(f"Data directories initialized at {self.data_dir}")
    
    def generate_recording_id(self) -> str:
        """Generate unique recording ID based on timestamp"""
        return datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    
    def get_recording_path(self, recording_id: str) -> Path:
        """Get path for recording file"""
        return self.data_dir / "recordings" / f"{recording_id}_meeting.wav"
    
    def get_transcript_path(self, recording_id: str) -> Path:
        """Get path for transcript file"""
        return self.data_dir / "transcripts" / f"{recording_id}_transcript.txt"
    
    def get_summary_path(self, recording_id: str) -> Path:
        """Get path for summary file"""
        return self.data_dir / "summaries" / f"{recording_id}_summary.md"
    
    def get_metadata_path(self, recording_id: str) -> Path:
        """Get path for metadata file"""
        return self.data_dir / "metadata" / f"{recording_id}_metadata.json"
    
    def get_export_path(self, recording_id: str, format: str = "pdf") -> Path:
        """Get path for exported file"""
        return self.data_dir / "exports" / f"{recording_id}_minutes.{format}"
    
    def create_recording_metadata(self, recording_id: str) -> RecordingMetadata:
        """Create initial metadata for a new recording"""
        metadata = RecordingMetadata(
            recording_id=recording_id,
            timestamp=datetime.now().isoformat()
        )
        
        self.save_metadata(metadata)
        return metadata
    
    def save_metadata(self, metadata: RecordingMetadata) -> None:
        """Save recording metadata to file"""
        try:
            metadata_path = self.get_metadata_path(metadata.recording_id)
            with open(metadata_path, 'w') as f:
                json.dump(asdict(metadata), f, indent=2)
            
            self.logger.debug(f"Metadata saved for {metadata.recording_id}")
            
        except Exception as e:
            self.logger.error(f"Failed to save metadata for {metadata.recording_id}: {e}")
    
    def load_metadata(self, recording_id: str) -> Optional[RecordingMetadata]:
        """Load recording metadata from file"""
        try:
            metadata_path = self.get_metadata_path(recording_id)
            if not metadata_path.exists():
                return None
            
            with open(metadata_path, 'r') as f:
                data = json.load(f)
            
            return RecordingMetadata(**data)
            
        except Exception as e:
            self.logger.error(f"Failed to load metadata for {recording_id}: {e}")
            return None
    
    def update_metadata(self, recording_id: str, **updates) -> None:
        """Update specific fields in metadata"""
        metadata = self.load_metadata(recording_id)
        if not metadata:
            self.logger.error(f"Cannot update metadata for {recording_id}: not found")
            return
        
        # Update fields
        for key, value in updates.items():
            if hasattr(metadata, key):
                setattr(metadata, key, value)
        
        self.save_metadata(metadata)
    
    def list_recordings(self) -> List[RecordingMetadata]:
        """List all recordings with metadata"""
        recordings = []
        metadata_dir = self.data_dir / "metadata"
        
        for metadata_file in metadata_dir.glob("*_metadata.json"):
            recording_id = metadata_file.stem.replace("_metadata", "")
            metadata = self.load_metadata(recording_id)
            if metadata:
                recordings.append(metadata)
        
        # Sort by timestamp (newest first)
        recordings.sort(key=lambda x: x.timestamp, reverse=True)
        return recordings
    
    def delete_recording(self, recording_id: str, confirm: bool = False) -> bool:
        """
        Delete recording and all associated files
        
        Args:
            recording_id: Recording ID to delete
            confirm: Safety confirmation
            
        Returns:
            True if deleted successfully
        """
        if not confirm:
            self.logger.warning(f"Delete operation requires confirmation for {recording_id}")
            return False
        
        try:
            files_to_delete = [
                self.get_recording_path(recording_id),
                self.get_transcript_path(recording_id),
                self.get_summary_path(recording_id),
                self.get_metadata_path(recording_id)
            ]
            
            # Add export files
            export_dir = self.data_dir / "exports"
            for export_file in export_dir.glob(f"{recording_id}_minutes.*"):
                files_to_delete.append(export_file)
            
            deleted_count = 0
            for file_path in files_to_delete:
                if file_path.exists():
                    file_path.unlink()
                    deleted_count += 1
            
            self.logger.info(f"Deleted {deleted_count} files for recording {recording_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to delete recording {recording_id}: {e}")
            return False
    
    def get_storage_usage(self) -> Dict[str, int]:
        """Get storage usage statistics"""
        usage = {
            "recordings": 0,
            "transcripts": 0,
            "summaries": 0,
            "exports": 0,
            "metadata": 0,
            "total": 0
        }
        
        try:
            for category in usage.keys():
                if category == "total":
                    continue
                
                directory = self.data_dir / category
                if directory.exists():
                    for file_path in directory.rglob("*"):
                        if file_path.is_file():
                            usage[category] += file_path.stat().st_size
            
            usage["total"] = sum(size for key, size in usage.items() if key != "total")
            
        except Exception as e:
            self.logger.error(f"Failed to calculate storage usage: {e}")
        
        return usage
    
    def cleanup_old_files(self, days: int = 30) -> int:
        """
        Clean up files older than specified days
        
        Args:
            days: Number of days to keep files
            
        Returns:
            Number of files cleaned up
        """
        if days < 1:
            self.logger.warning("Cleanup days must be at least 1")
            return 0
        
        from datetime import timedelta
        cutoff_date = datetime.now() - timedelta(days=days)
        
        cleaned_count = 0
        recordings = self.list_recordings()
        
        for metadata in recordings:
            try:
                recording_date = datetime.fromisoformat(metadata.timestamp)
                if recording_date < cutoff_date:
                    if self.delete_recording(metadata.recording_id, confirm=True):
                        cleaned_count += 1
            except Exception as e:
                self.logger.error(f"Error processing {metadata.recording_id} for cleanup: {e}")
        
        self.logger.info(f"Cleaned up {cleaned_count} old recordings")
        return cleaned_count
    
    def export_metadata_summary(self, output_path: Optional[Path] = None) -> Path:
        """Export summary of all recordings metadata to JSON"""
        if output_path is None:
            output_path = self.data_dir / "metadata_summary.json"
        
        recordings_data = []
        for metadata in self.list_recordings():
            recordings_data.append(asdict(metadata))
        
        with open(output_path, 'w') as f:
            json.dump({
                "export_date": datetime.now().isoformat(),
                "total_recordings": len(recordings_data),
                "recordings": recordings_data
            }, f, indent=2)
        
        self.logger.info(f"Metadata summary exported to {output_path}")
        return output_path