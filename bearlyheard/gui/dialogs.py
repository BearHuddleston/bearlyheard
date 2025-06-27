"""Dialog windows for BearlyHeard"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTextEdit, QPushButton, 
    QLabel, QTabWidget, QWidget, QSplitter, QMessageBox, QFileDialog
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont

from ..utils.logger import LoggerMixin


class TranscriptViewerDialog(QDialog, LoggerMixin):
    """Dialog for viewing and editing transcripts"""
    
    # Signals
    transcript_saved = pyqtSignal(str)  # transcript text
    
    def __init__(self, recording_id: str, transcript_text: str = "", parent=None):
        """
        Initialize transcript viewer
        
        Args:
            recording_id: Recording ID
            transcript_text: Initial transcript text
            parent: Parent widget
        """
        super().__init__(parent)
        self.recording_id = recording_id
        self.original_transcript = transcript_text
        self.current_transcript = transcript_text
        
        self._setup_ui()
        self._load_transcript()
        
    def _setup_ui(self):
        """Setup the user interface"""
        self.setWindowTitle(f"Transcript Viewer - {self.recording_id}")
        self.setMinimumSize(800, 600)
        self.resize(1000, 700)
        
        layout = QVBoxLayout(self)
        
        # Header
        header_layout = QHBoxLayout()
        
        title_label = QLabel(f"Transcript: {self.recording_id}")
        title_label.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        header_layout.addWidget(title_label)
        
        header_layout.addStretch()
        
        layout.addLayout(header_layout)
        
        # Main content area
        self.tab_widget = QTabWidget()
        
        # Transcript tab
        transcript_tab = QWidget()
        transcript_layout = QVBoxLayout(transcript_tab)
        
        # Transcript editor
        self.transcript_editor = QTextEdit()
        self.transcript_editor.setFont(QFont("Consolas", 10))
        self.transcript_editor.textChanged.connect(self._on_transcript_changed)
        transcript_layout.addWidget(self.transcript_editor)
        
        # Transcript buttons
        transcript_buttons = QHBoxLayout()
        
        self.save_transcript_btn = QPushButton("Save Transcript")
        self.save_transcript_btn.clicked.connect(self._save_transcript)
        self.save_transcript_btn.setEnabled(False)
        transcript_buttons.addWidget(self.save_transcript_btn)
        
        self.export_transcript_btn = QPushButton("Export...")
        self.export_transcript_btn.clicked.connect(self._export_transcript)
        transcript_buttons.addWidget(self.export_transcript_btn)
        
        self.revert_transcript_btn = QPushButton("Revert Changes")
        self.revert_transcript_btn.clicked.connect(self._revert_transcript)
        self.revert_transcript_btn.setEnabled(False)
        transcript_buttons.addWidget(self.revert_transcript_btn)
        
        transcript_buttons.addStretch()
        transcript_layout.addLayout(transcript_buttons)
        
        self.tab_widget.addTab(transcript_tab, "Transcript")
        
        # Summary tab (placeholder for future integration)
        summary_tab = QWidget()
        summary_layout = QVBoxLayout(summary_tab)
        
        summary_label = QLabel("Summary functionality will be integrated here")
        summary_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        summary_layout.addWidget(summary_label)
        
        self.tab_widget.addTab(summary_tab, "Summary")
        
        layout.addWidget(self.tab_widget)
        
        # Dialog buttons
        button_layout = QHBoxLayout()
        
        self.close_btn = QPushButton("Close")
        self.close_btn.clicked.connect(self.accept)
        button_layout.addStretch()
        button_layout.addWidget(self.close_btn)
        
        layout.addLayout(button_layout)
    
    def _load_transcript(self):
        """Load transcript into editor"""
        self.transcript_editor.setPlainText(self.current_transcript)
    
    def _on_transcript_changed(self):
        """Handle transcript text changes"""
        self.current_transcript = self.transcript_editor.toPlainText()
        has_changes = self.current_transcript != self.original_transcript
        
        self.save_transcript_btn.setEnabled(has_changes)
        self.revert_transcript_btn.setEnabled(has_changes)
    
    def _save_transcript(self):
        """Save transcript changes"""
        try:
            self.original_transcript = self.current_transcript
            self.transcript_saved.emit(self.current_transcript)
            
            # Update button states
            self.save_transcript_btn.setEnabled(False)
            self.revert_transcript_btn.setEnabled(False)
            
            # Show confirmation
            self.statusBar().showMessage("Transcript saved", 3000)
            
        except Exception as e:
            QMessageBox.critical(self, "Save Error", f"Failed to save transcript: {e}")
    
    def _revert_transcript(self):
        """Revert transcript to original"""
        self.current_transcript = self.original_transcript
        self.transcript_editor.setPlainText(self.original_transcript)
    
    def _export_transcript(self):
        """Export transcript to file"""
        try:
            file_path, _ = QFileDialog.getSaveFileName(
                self,
                "Export Transcript",
                f"{self.recording_id}_transcript.txt",
                "Text Files (*.txt);;All Files (*)"
            )
            
            if file_path:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(self.current_transcript)
                
                QMessageBox.information(self, "Export Complete", f"Transcript exported to:\n{file_path}")
                
        except Exception as e:
            QMessageBox.critical(self, "Export Error", f"Failed to export transcript: {e}")


class SummaryDialog(QDialog, LoggerMixin):
    """Dialog for viewing and managing summaries"""
    
    def __init__(self, recording_id: str, summary_data: dict = None, parent=None):
        """
        Initialize summary dialog
        
        Args:
            recording_id: Recording ID
            summary_data: Summary data dictionary
            parent: Parent widget
        """
        super().__init__(parent)
        self.recording_id = recording_id
        self.summary_data = summary_data or {}
        
        self._setup_ui()
        self._load_summary()
        
    def _setup_ui(self):
        """Setup the user interface"""
        self.setWindowTitle(f"Meeting Summary - {self.recording_id}")
        self.setMinimumSize(700, 500)
        self.resize(900, 600)
        
        layout = QVBoxLayout(self)
        
        # Header
        header_layout = QHBoxLayout()
        
        title_label = QLabel(f"Summary: {self.recording_id}")
        title_label.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        header_layout.addWidget(title_label)
        
        header_layout.addStretch()
        
        layout.addLayout(header_layout)
        
        # Summary content
        self.summary_editor = QTextEdit()
        self.summary_editor.setFont(QFont("Arial", 11))
        self.summary_editor.setReadOnly(True)
        layout.addWidget(self.summary_editor)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        self.export_btn = QPushButton("Export Summary...")
        self.export_btn.clicked.connect(self._export_summary)
        button_layout.addWidget(self.export_btn)
        
        self.regenerate_btn = QPushButton("Regenerate Summary")
        self.regenerate_btn.clicked.connect(self._regenerate_summary)
        button_layout.addWidget(self.regenerate_btn)
        
        button_layout.addStretch()
        
        self.close_btn = QPushButton("Close")
        self.close_btn.clicked.connect(self.accept)
        button_layout.addWidget(self.close_btn)
        
        layout.addLayout(button_layout)
    
    def _load_summary(self):
        """Load summary into display"""
        if not self.summary_data:
            self.summary_editor.setPlainText("No summary available")
            return
        
        # Format summary for display
        formatted_summary = self._format_summary_display()
        self.summary_editor.setHtml(formatted_summary)
    
    def _format_summary_display(self) -> str:
        """Format summary data for HTML display"""
        html = "<h2>Meeting Summary</h2>"
        
        if "summary" in self.summary_data:
            html += f"<h3>Overview</h3><p>{self.summary_data['summary']}</p>"
        
        if "key_points" in self.summary_data and self.summary_data["key_points"]:
            html += "<h3>Key Points</h3><ul>"
            for point in self.summary_data["key_points"]:
                html += f"<li>{point}</li>"
            html += "</ul>"
        
        if "action_items" in self.summary_data and self.summary_data["action_items"]:
            html += "<h3>Action Items</h3><ul>"
            for item in self.summary_data["action_items"]:
                html += f"<li>{item}</li>"
            html += "</ul>"
        
        if "decisions" in self.summary_data and self.summary_data["decisions"]:
            html += "<h3>Decisions</h3><ul>"
            for decision in self.summary_data["decisions"]:
                html += f"<li>{decision}</li>"
            html += "</ul>"
        
        if "participants" in self.summary_data and self.summary_data["participants"]:
            html += "<h3>Participants</h3><ul>"
            for participant in self.summary_data["participants"]:
                html += f"<li>{participant}</li>"
            html += "</ul>"
        
        return html
    
    def _export_summary(self):
        """Export summary to file"""
        try:
            file_path, _ = QFileDialog.getSaveFileName(
                self,
                "Export Summary",
                f"{self.recording_id}_summary.html",
                "HTML Files (*.html);;Text Files (*.txt);;All Files (*)"
            )
            
            if file_path:
                if file_path.endswith('.html'):
                    content = self._format_summary_display()
                else:
                    content = self.summary_editor.toPlainText()
                
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                
                QMessageBox.information(self, "Export Complete", f"Summary exported to:\n{file_path}")
                
        except Exception as e:
            QMessageBox.critical(self, "Export Error", f"Failed to export summary: {e}")
    
    def _regenerate_summary(self):
        """Regenerate summary (placeholder)"""
        QMessageBox.information(
            self,
            "Regenerate Summary",
            "Summary regeneration will be implemented with the summarization worker integration."
        )