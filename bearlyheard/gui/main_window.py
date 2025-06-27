"""Main window for BearlyHeard application"""

import sys
from typing import Optional
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QPushButton, QLabel, QComboBox, QFrame, QListWidget, QListWidgetItem,
    QProgressBar, QMenuBar, QMenu, QStatusBar, QApplication, QMessageBox
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QThread
from PyQt6.QtGui import QAction, QFont, QIcon

from ..utils.logger import LoggerMixin
from ..utils.config import Config
from ..utils.file_manager import FileManager
from ..audio.devices import AudioDeviceManager, AudioDevice
from .themes import ThemeManager


class MainWindow(QMainWindow, LoggerMixin):
    """Main application window"""
    
    # Signals
    recording_started = pyqtSignal()
    recording_stopped = pyqtSignal()
    
    def __init__(self):
        super().__init__()
        
        # Initialize managers
        self.config = Config()
        self.file_manager = FileManager()
        self.audio_device_manager = AudioDeviceManager()
        self.theme_manager = ThemeManager()
        
        # State variables
        self.is_recording = False
        self.recording_start_time = None
        self.current_recording_id = None
        
        # Timer for updating recording duration
        self.timer = QTimer()
        self.timer.timeout.connect(self._update_timer)
        
        # Setup UI
        self._setup_ui()
        self._setup_menu()
        self._setup_connections()
        self._load_audio_devices()
        self._refresh_recordings_list()
        
        self.logger.info("Main window initialized")
    
    def _setup_ui(self):
        """Setup the user interface"""
        self.setWindowTitle("BearlyHeard - Meeting Recorder")
        self.setMinimumSize(800, 600)
        
        # Central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Main layout
        layout = QVBoxLayout(central_widget)
        layout.setSpacing(20)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # Audio sources section
        layout.addWidget(self._create_audio_sources_section())
        
        # Recording controls section
        layout.addWidget(self._create_recording_controls_section())
        
        # Status section
        layout.addWidget(self._create_status_section())
        
        # Recent recordings section
        layout.addWidget(self._create_recordings_section())
        
        # Status bar
        self.statusBar().showMessage("Ready to record")
    
    def _create_audio_sources_section(self) -> QFrame:
        """Create audio sources selection section"""
        frame = QFrame()
        frame.setFrameStyle(QFrame.Shape.Box)
        frame.setMaximumHeight(120)
        
        layout = QGridLayout(frame)
        layout.setSpacing(10)
        
        # Title
        title = QLabel("Audio Sources")
        title.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        layout.addWidget(title, 0, 0, 1, 2)
        
        # Application audio selection
        layout.addWidget(QLabel("Application:"), 1, 0)
        self.app_audio_combo = QComboBox()
        self.app_audio_combo.setMinimumWidth(300)
        layout.addWidget(self.app_audio_combo, 1, 1)
        
        # Microphone selection
        layout.addWidget(QLabel("Microphone:"), 2, 0)
        self.mic_audio_combo = QComboBox()
        self.mic_audio_combo.setMinimumWidth(300)
        layout.addWidget(self.mic_audio_combo, 2, 1)
        
        # Refresh button
        refresh_btn = QPushButton("Refresh Devices")
        refresh_btn.clicked.connect(self._refresh_audio_devices)
        layout.addWidget(refresh_btn, 1, 2)
        
        return frame
    
    def _create_recording_controls_section(self) -> QFrame:
        """Create recording controls section"""
        frame = QFrame()
        frame.setFrameStyle(QFrame.Shape.Box)
        frame.setMaximumHeight(150)
        
        layout = QVBoxLayout(frame)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Record/Stop button
        self.record_button = QPushButton("● Record")
        self.record_button.setObjectName("recordButton")
        self.record_button.clicked.connect(self._toggle_recording)
        layout.addWidget(self.record_button)
        
        # Timer display
        self.timer_label = QLabel("00:00:00")
        self.timer_label.setObjectName("timerLabel")
        self.timer_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.timer_label)
        
        # Audio levels placeholder
        self.audio_levels_label = QLabel("▁▃▅▇▅▃▁ Audio Levels")
        self.audio_levels_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.audio_levels_label)
        
        return frame
    
    def _create_status_section(self) -> QFrame:
        """Create status section"""
        frame = QFrame()
        frame.setFrameStyle(QFrame.Shape.Box)
        frame.setMaximumHeight(60)
        
        layout = QHBoxLayout(frame)
        
        # Status label
        layout.addWidget(QLabel("Status:"))
        self.status_label = QLabel("Ready to record")
        self.status_label.setObjectName("statusLabel")
        layout.addWidget(self.status_label)
        
        # Progress bar (hidden by default)
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)
        
        layout.addStretch()
        
        return frame
    
    def _create_recordings_section(self) -> QFrame:
        """Create recent recordings section"""
        frame = QFrame()
        frame.setFrameStyle(QFrame.Shape.Box)
        
        layout = QVBoxLayout(frame)
        
        # Title
        title = QLabel("Recent Recordings")
        title.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        layout.addWidget(title)
        
        # Recordings list
        self.recordings_list = QListWidget()
        self.recordings_list.itemDoubleClicked.connect(self._on_recording_double_clicked)
        layout.addWidget(self.recordings_list)
        
        # Action buttons
        buttons_layout = QHBoxLayout()
        
        self.play_button = QPushButton("▶ Play")
        self.play_button.clicked.connect(self._play_selected_recording)
        self.play_button.setEnabled(False)
        buttons_layout.addWidget(self.play_button)
        
        self.transcribe_button = QPushButton("📝 Transcribe")
        self.transcribe_button.clicked.connect(self._transcribe_selected_recording)
        self.transcribe_button.setEnabled(False)
        buttons_layout.addWidget(self.transcribe_button)
        
        self.summarize_button = QPushButton("📊 Summarize")
        self.summarize_button.clicked.connect(self._summarize_selected_recording)
        self.summarize_button.setEnabled(False)
        buttons_layout.addWidget(self.summarize_button)
        
        self.delete_button = QPushButton("🗑 Delete")
        self.delete_button.clicked.connect(self._delete_selected_recording)
        self.delete_button.setEnabled(False)
        buttons_layout.addWidget(self.delete_button)
        
        buttons_layout.addStretch()
        layout.addLayout(buttons_layout)
        
        return frame
    
    def _setup_menu(self):
        """Setup menu bar"""
        menubar = self.menuBar()
        
        # File menu
        file_menu = menubar.addMenu("File")
        
        new_recording_action = QAction("New Recording", self)
        new_recording_action.setShortcut("Ctrl+N")
        new_recording_action.triggered.connect(self._start_recording)
        file_menu.addAction(new_recording_action)
        
        file_menu.addSeparator()
        
        exit_action = QAction("Exit", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        # View menu
        view_menu = menubar.addMenu("View")
        
        toggle_theme_action = QAction("Toggle Theme", self)
        toggle_theme_action.setShortcut("Ctrl+T")
        toggle_theme_action.triggered.connect(self._toggle_theme)
        view_menu.addAction(toggle_theme_action)
        
        refresh_action = QAction("Refresh", self)
        refresh_action.setShortcut("F5")
        refresh_action.triggered.connect(self._refresh_all)
        view_menu.addAction(refresh_action)
        
        # Tools menu
        tools_menu = menubar.addMenu("Tools")
        
        settings_action = QAction("Settings", self)
        settings_action.triggered.connect(self._open_settings)
        tools_menu.addAction(settings_action)
        
        # Help menu
        help_menu = menubar.addMenu("Help")
        
        about_action = QAction("About", self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)
    
    def _setup_connections(self):
        """Setup signal connections"""
        # Recording list selection
        self.recordings_list.itemSelectionChanged.connect(self._on_recording_selection_changed)
        
        # Theme manager
        self.theme_manager.theme_changed.connect(self._on_theme_changed)
    
    def _load_audio_devices(self):
        """Load audio devices into combo boxes"""
        # Clear existing items
        self.app_audio_combo.clear()
        self.mic_audio_combo.clear()
        
        # Add placeholder
        self.app_audio_combo.addItem("Select application audio source...")
        self.mic_audio_combo.addItem("Select microphone...")
        
        try:
            # Load loopback devices for application audio
            loopback_devices = self.audio_device_manager.get_loopback_devices()
            for device in loopback_devices:
                self.app_audio_combo.addItem(device.name, device)
            
            # Load input devices for microphone
            input_devices = self.audio_device_manager.get_input_devices()
            for device in input_devices:
                self.mic_audio_combo.addItem(device.name, device)
            
            # Set default selections
            default_input = self.audio_device_manager.get_default_input_device()
            if default_input:
                for i in range(1, self.mic_audio_combo.count()):
                    if self.mic_audio_combo.itemData(i) == default_input:
                        self.mic_audio_combo.setCurrentIndex(i)
                        break
                        
        except Exception as e:
            self.logger.error(f"Failed to load audio devices: {e}")
            self._show_error("Audio Device Error", f"Failed to load audio devices: {e}")
    
    def _refresh_audio_devices(self):
        """Refresh audio device list"""
        self.audio_device_manager.refresh_devices()
        self._load_audio_devices()
        self.statusBar().showMessage("Audio devices refreshed", 3000)
    
    def _refresh_recordings_list(self):
        """Refresh recordings list"""
        self.recordings_list.clear()
        
        try:
            recordings = self.file_manager.list_recordings()
            for metadata in recordings:
                item_text = f"📁 {metadata.recording_id} ({metadata.duration})"
                item = QListWidgetItem(item_text)
                item.setData(Qt.ItemDataRole.UserRole, metadata)
                self.recordings_list.addItem(item)
                
        except Exception as e:
            self.logger.error(f"Failed to refresh recordings list: {e}")
    
    def _toggle_recording(self):
        """Toggle recording state"""
        if self.is_recording:
            self._stop_recording()
        else:
            self._start_recording()
    
    def _start_recording(self):
        """Start recording"""
        # Validate audio sources
        if self.app_audio_combo.currentIndex() == 0 and self.mic_audio_combo.currentIndex() == 0:
            self._show_error("No Audio Source", "Please select at least one audio source.")
            return
        
        try:
            # Generate recording ID
            self.current_recording_id = self.file_manager.generate_recording_id()
            
            # Create metadata
            metadata = self.file_manager.create_recording_metadata(self.current_recording_id)
            
            # Update UI
            self.is_recording = True
            self.record_button.setText("■ Stop")
            self.status_label.setText("Recording...")
            
            # Start timer
            self.recording_start_time = 0
            self.timer.start(1000)  # Update every second
            
            # Disable device selection while recording
            self.app_audio_combo.setEnabled(False)
            self.mic_audio_combo.setEnabled(False)
            
            self.recording_started.emit()
            self.logger.info(f"Recording started: {self.current_recording_id}")
            
        except Exception as e:
            self.logger.error(f"Failed to start recording: {e}")
            self._show_error("Recording Error", f"Failed to start recording: {e}")
    
    def _stop_recording(self):
        """Stop recording"""
        try:
            self.is_recording = False
            self.timer.stop()
            
            # Update UI
            self.record_button.setText("● Record")
            self.status_label.setText("Recording saved")
            self.timer_label.setText("00:00:00")
            
            # Re-enable device selection
            self.app_audio_combo.setEnabled(True)
            self.mic_audio_combo.setEnabled(True)
            
            # Update recording metadata
            duration = self._format_duration(self.recording_start_time)
            self.file_manager.update_metadata(
                self.current_recording_id,
                duration=duration
            )
            
            self.recording_stopped.emit()
            self.logger.info(f"Recording stopped: {self.current_recording_id}")
            
            # Refresh recordings list
            self._refresh_recordings_list()
            
            # Show post-recording dialog
            self._show_post_recording_dialog()
            
        except Exception as e:
            self.logger.error(f"Failed to stop recording: {e}")
            self._show_error("Recording Error", f"Failed to stop recording: {e}")
    
    def _update_timer(self):
        """Update recording timer"""
        self.recording_start_time += 1
        time_text = self._format_duration(self.recording_start_time)
        self.timer_label.setText(time_text)
    
    def _format_duration(self, seconds: int) -> str:
        """Format duration in HH:MM:SS format"""
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        secs = seconds % 60
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    
    def _show_post_recording_dialog(self):
        """Show dialog after recording completion"""
        from PyQt6.QtWidgets import QDialog, QDialogButtonBox
        
        msg = QMessageBox(self)
        msg.setWindowTitle("Recording Complete")
        msg.setText(f"Recording saved: {self.current_recording_id}")
        msg.setInformativeText("What would you like to do next?")
        
        transcribe_btn = msg.addButton("Transcribe Now", QMessageBox.ButtonRole.ActionRole)
        save_btn = msg.addButton("Save Only", QMessageBox.ButtonRole.AcceptRole)
        discard_btn = msg.addButton("Discard", QMessageBox.ButtonRole.DestructiveRole)
        
        msg.exec()
        
        if msg.clickedButton() == transcribe_btn:
            self._transcribe_recording(self.current_recording_id)
        elif msg.clickedButton() == discard_btn:
            self._delete_recording(self.current_recording_id, confirm=True)
    
    def _on_recording_selection_changed(self):
        """Handle recording selection change"""
        has_selection = bool(self.recordings_list.currentItem())
        
        self.play_button.setEnabled(has_selection)
        self.transcribe_button.setEnabled(has_selection)
        self.summarize_button.setEnabled(has_selection)
        self.delete_button.setEnabled(has_selection)
    
    def _on_recording_double_clicked(self, item: QListWidgetItem):
        """Handle double-click on recording item"""
        self._play_selected_recording()
    
    def _play_selected_recording(self):
        """Play selected recording"""
        item = self.recordings_list.currentItem()
        if not item:
            return
        
        metadata = item.data(Qt.ItemDataRole.UserRole)
        self.logger.info(f"Playing recording: {metadata.recording_id}")
        # TODO: Implement audio playback
        self.statusBar().showMessage(f"Playing: {metadata.recording_id}", 3000)
    
    def _transcribe_selected_recording(self):
        """Transcribe selected recording"""
        item = self.recordings_list.currentItem()
        if not item:
            return
        
        metadata = item.data(Qt.ItemDataRole.UserRole)
        self._transcribe_recording(metadata.recording_id)
    
    def _transcribe_recording(self, recording_id: str):
        """Transcribe a recording"""
        self.logger.info(f"Starting transcription: {recording_id}")
        # TODO: Implement transcription
        self.statusBar().showMessage(f"Transcribing: {recording_id}", 3000)
    
    def _summarize_selected_recording(self):
        """Summarize selected recording"""
        item = self.recordings_list.currentItem()
        if not item:
            return
        
        metadata = item.data(Qt.ItemDataRole.UserRole)
        self.logger.info(f"Starting summarization: {metadata.recording_id}")
        # TODO: Implement summarization
        self.statusBar().showMessage(f"Summarizing: {metadata.recording_id}", 3000)
    
    def _delete_selected_recording(self):
        """Delete selected recording"""
        item = self.recordings_list.currentItem()
        if not item:
            return
        
        metadata = item.data(Qt.ItemDataRole.UserRole)
        
        reply = QMessageBox.question(
            self,
            "Confirm Delete",
            f"Are you sure you want to delete recording '{metadata.recording_id}'?\n\n"
            "This will remove the recording file, transcript, and summary.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self._delete_recording(metadata.recording_id, confirm=True)
    
    def _delete_recording(self, recording_id: str, confirm: bool = False):
        """Delete a recording"""
        if self.file_manager.delete_recording(recording_id, confirm=confirm):
            self._refresh_recordings_list()
            self.statusBar().showMessage(f"Deleted: {recording_id}", 3000)
        else:
            self._show_error("Delete Error", f"Failed to delete recording: {recording_id}")
    
    def _toggle_theme(self):
        """Toggle application theme"""
        app = QApplication.instance()
        new_theme = self.theme_manager.toggle_theme(app)
        self.config.set("ui.theme", new_theme)
    
    def _on_theme_changed(self, theme: str):
        """Handle theme change"""
        self.statusBar().showMessage(f"Theme changed to: {theme}", 3000)
    
    def _refresh_all(self):
        """Refresh all data"""
        self._refresh_audio_devices()
        self._refresh_recordings_list()
        self.statusBar().showMessage("All data refreshed", 3000)
    
    def _open_settings(self):
        """Open settings dialog"""
        # TODO: Implement settings dialog
        self.statusBar().showMessage("Settings dialog not implemented yet", 3000)
    
    def _show_about(self):
        """Show about dialog"""
        QMessageBox.about(
            self,
            "About BearlyHeard",
            "BearlyHeard v0.1.0\n\n"
            "AI-powered meeting recorder with transcription and summarization.\n\n"
            "Built with PyQt6 and powered by Whisper AI."
        )
    
    def _show_error(self, title: str, message: str):
        """Show error message dialog"""
        QMessageBox.critical(self, title, message)
    
    def closeEvent(self, event):
        """Handle window close event"""
        if self.is_recording:
            reply = QMessageBox.question(
                self,
                "Recording in Progress",
                "A recording is currently in progress. Do you want to stop and exit?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            
            if reply == QMessageBox.StandardButton.Yes:
                self._stop_recording()
                event.accept()
            else:
                event.ignore()
        else:
            event.accept()