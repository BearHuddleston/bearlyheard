"""Background worker threads for BearlyHeard GUI"""

from pathlib import Path
from PyQt6.QtCore import QThread, pyqtSignal, QObject

from ..ml.transcriber import Transcriber, TranscriptionResult
from ..ml.summarizer import Summarizer
from ..utils.logger import LoggerMixin


class TranscriptionWorker(QThread, LoggerMixin):
    """Background worker for audio transcription"""
    
    # Signals
    progress_updated = pyqtSignal(float)  # Progress percentage (0.0 to 1.0)
    transcription_completed = pyqtSignal(object)  # TranscriptionResult
    transcription_failed = pyqtSignal(str)  # Error message
    
    def __init__(self, audio_file: str, model_size: str = "base", language: str = None):
        """
        Initialize transcription worker
        
        Args:
            audio_file: Path to audio file to transcribe
            model_size: Whisper model size
            language: Language code (auto-detect if None)
        """
        super().__init__()
        self.audio_file = Path(audio_file)
        self.model_size = model_size
        self.language = language
        self.transcriber = None
        
    def run(self):
        """Run transcription in background thread"""
        try:
            self.logger.info(f"Starting background transcription of {self.audio_file}")
            
            # Initialize transcriber
            self.transcriber = Transcriber(model_size=self.model_size)
            
            # Set up progress callback
            self.transcriber.set_progress_callback(self._on_progress_update)
            
            # Emit initial progress
            self.progress_updated.emit(0.0)
            
            # Perform transcription
            result = self.transcriber.transcribe(
                str(self.audio_file),
                language=self.language
            )
            
            if result:
                self.logger.info(f"Transcription completed successfully")
                self.transcription_completed.emit(result)
            else:
                self.logger.error("Transcription failed: no result returned")
                self.transcription_failed.emit("Transcription failed: no result returned")
                
        except Exception as e:
            error_msg = f"Transcription error: {str(e)}"
            self.logger.error(error_msg)
            self.transcription_failed.emit(error_msg)
        
        finally:
            # Clean up model to free memory
            if self.transcriber:
                self.transcriber.clear_model()
    
    def _on_progress_update(self, progress: float):
        """Handle progress updates from transcriber"""
        self.progress_updated.emit(progress)


class SummarizationWorker(QThread, LoggerMixin):
    """Background worker for text summarization"""
    
    # Signals
    progress_updated = pyqtSignal(float)  # Progress percentage (0.0 to 1.0)
    summarization_completed = pyqtSignal(dict)  # Summary result
    summarization_failed = pyqtSignal(str)  # Error message
    
    def __init__(self, transcript_text: str, summary_type: str = "executive"):
        """
        Initialize summarization worker
        
        Args:
            transcript_text: Text to summarize
            summary_type: Type of summary (executive, detailed, action_items)
        """
        super().__init__()
        self.transcript_text = transcript_text
        self.summary_type = summary_type
        self.summarizer = None
        
    def run(self):
        """Run summarization in background thread"""
        try:
            self.logger.info(f"Starting background summarization ({self.summary_type})")
            
            # Initialize summarizer
            self.summarizer = Summarizer()
            
            # Set up progress callback
            self.summarizer.set_progress_callback(self._on_progress_update)
            
            # Emit initial progress
            self.progress_updated.emit(0.0)
            
            # Perform summarization
            result = self.summarizer.summarize(
                self.transcript_text,
                summary_type=self.summary_type
            )
            
            if result:
                self.logger.info(f"Summarization completed successfully")
                # Convert SummaryResult to dict for signal emission
                result_dict = {
                    'summary': result.summary,
                    'action_items': result.action_items,
                    'key_points': result.key_points,
                    'participants': result.participants,
                    'decisions': result.decisions,
                    'summary_type': result.summary_type,
                    'model_name': result.model_name
                }
                self.summarization_completed.emit(result_dict)
            else:
                self.logger.error("Summarization failed: no result returned")
                self.summarization_failed.emit("Summarization failed: no result returned")
                
        except Exception as e:
            error_msg = f"Summarization error: {str(e)}"
            self.logger.error(error_msg)
            self.summarization_failed.emit(error_msg)
        
        finally:
            # Clean up model to free memory
            if self.summarizer:
                self.summarizer.clear_model()
    
    def _on_progress_update(self, progress: float):
        """Handle progress updates from summarizer"""
        self.progress_updated.emit(progress)


class BatchTranscriptionWorker(QThread, LoggerMixin):
    """Background worker for batch transcription of multiple files"""
    
    # Signals
    progress_updated = pyqtSignal(float)  # Overall progress (0.0 to 1.0)
    file_progress_updated = pyqtSignal(str, float)  # File-specific progress
    file_completed = pyqtSignal(str, object)  # Filename and result
    file_failed = pyqtSignal(str, str)  # Filename and error message
    batch_completed = pyqtSignal(list)  # List of results
    
    def __init__(self, audio_files: list, model_size: str = "base", language: str = None):
        """
        Initialize batch transcription worker
        
        Args:
            audio_files: List of audio file paths
            model_size: Whisper model size
            language: Language code (auto-detect if None)
        """
        super().__init__()
        self.audio_files = [Path(f) for f in audio_files]
        self.model_size = model_size
        self.language = language
        self.transcriber = None
        self.results = []
        
    def run(self):
        """Run batch transcription in background thread"""
        try:
            self.logger.info(f"Starting batch transcription of {len(self.audio_files)} files")
            
            # Initialize transcriber once for all files
            self.transcriber = Transcriber(model_size=self.model_size)
            
            if not self.transcriber.load_model():
                self.file_failed.emit("", "Failed to load Whisper model")
                return
            
            # Process each file
            for i, audio_file in enumerate(self.audio_files):
                try:
                    # Set up progress callback for this file
                    self.transcriber.set_progress_callback(
                        lambda progress: self.file_progress_updated.emit(str(audio_file), progress)
                    )
                    
                    # Transcribe file
                    result = self.transcriber.transcribe(
                        str(audio_file),
                        language=self.language
                    )
                    
                    if result:
                        self.results.append((str(audio_file), result))
                        self.file_completed.emit(str(audio_file), result)
                    else:
                        self.file_failed.emit(str(audio_file), "Transcription failed")
                    
                    # Update overall progress
                    overall_progress = (i + 1) / len(self.audio_files)
                    self.progress_updated.emit(overall_progress)
                    
                except Exception as e:
                    error_msg = f"Error processing {audio_file}: {str(e)}"
                    self.logger.error(error_msg)
                    self.file_failed.emit(str(audio_file), error_msg)
            
            # Emit batch completion
            self.batch_completed.emit(self.results)
            self.logger.info(f"Batch transcription completed: {len(self.results)}/{len(self.audio_files)} successful")
            
        except Exception as e:
            error_msg = f"Batch transcription error: {str(e)}"
            self.logger.error(error_msg)
            self.file_failed.emit("", error_msg)
        
        finally:
            # Clean up model
            if self.transcriber:
                self.transcriber.clear_model()


class ModelDownloadWorker(QThread, LoggerMixin):
    """Background worker for downloading AI models"""
    
    # Signals
    progress_updated = pyqtSignal(str, float)  # Model name and progress
    download_completed = pyqtSignal(str)  # Model name
    download_failed = pyqtSignal(str, str)  # Model name and error message
    
    def __init__(self, model_names: list):
        """
        Initialize model download worker
        
        Args:
            model_names: List of model names to download
        """
        super().__init__()
        self.model_names = model_names
        
    def run(self):
        """Download models in background"""
        try:
            for model_name in self.model_names:
                try:
                    self.logger.info(f"Downloading model: {model_name}")
                    self.progress_updated.emit(model_name, 0.0)
                    
                    # Initialize transcriber/summarizer to trigger download
                    if "whisper" in model_name.lower():
                        transcriber = Transcriber(model_size=model_name)
                        if transcriber.load_model():
                            self.download_completed.emit(model_name)
                            transcriber.clear_model()
                        else:
                            self.download_failed.emit(model_name, "Failed to load model")
                    
                    self.progress_updated.emit(model_name, 1.0)
                    
                except Exception as e:
                    error_msg = f"Failed to download {model_name}: {str(e)}"
                    self.logger.error(error_msg)
                    self.download_failed.emit(model_name, error_msg)
                    
        except Exception as e:
            self.logger.error(f"Model download worker error: {str(e)}")
            self.download_failed.emit("", str(e))