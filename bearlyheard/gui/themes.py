"""Theme management for BearlyHeard GUI"""

from typing import Dict, Optional
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QObject, pyqtSignal

try:
    import qdarktheme
    HAS_QDARKTHEME = True
except ImportError:
    HAS_QDARKTHEME = False

from ..utils.logger import LoggerMixin


class ThemeManager(QObject, LoggerMixin):
    """Manages application themes and styling"""
    
    # Signal emitted when theme changes
    theme_changed = pyqtSignal(str)
    
    def __init__(self):
        super().__init__()
        self.current_theme = "dark"
        self.available_themes = ["dark", "light", "auto"]
        
        if not HAS_QDARKTHEME:
            self.logger.warning("qdarktheme not available, using fallback themes")
    
    def get_available_themes(self) -> Dict[str, str]:
        """Get available themes"""
        themes = {
            "dark": "Dark Theme",
            "light": "Light Theme"
        }
        
        if HAS_QDARKTHEME:
            themes["auto"] = "Auto (System)"
        
        return themes
    
    def apply_theme(self, app: QApplication, theme: str = "dark") -> None:
        """
        Apply theme to application
        
        Args:
            app: QApplication instance
            theme: Theme name ("dark", "light", "auto")
        """
        try:
            if HAS_QDARKTHEME:
                self._apply_qdarktheme(app, theme)
            else:
                self._apply_fallback_theme(app, theme)
            
            self.current_theme = theme
            self.theme_changed.emit(theme)
            self.logger.info(f"Applied theme: {theme}")
            
        except Exception as e:
            self.logger.error(f"Failed to apply theme {theme}: {e}")
            # Fallback to default
            if theme != "dark":
                self.apply_theme(app, "dark")
    
    def _apply_qdarktheme(self, app: QApplication, theme: str) -> None:
        """Apply theme using qdarktheme library"""
        if theme == "auto":
            qdarktheme.setup_theme("auto")
        elif theme == "light":
            qdarktheme.setup_theme("light")
        else:
            qdarktheme.setup_theme("dark")
    
    def _apply_fallback_theme(self, app: QApplication, theme: str) -> None:
        """Apply fallback theme using custom CSS"""
        if theme == "light":
            app.setStyleSheet(self._get_light_theme_css())
        else:
            app.setStyleSheet(self._get_dark_theme_css())
    
    def _get_dark_theme_css(self) -> str:
        """Get dark theme CSS"""
        return """
        QWidget {
            background-color: #2b2b2b;
            color: #ffffff;
            font-family: 'Segoe UI', Arial, sans-serif;
        }
        
        QMainWindow {
            background-color: #2b2b2b;
        }
        
        QFrame {
            background-color: #3c3c3c;
            border: 1px solid #555555;
            border-radius: 4px;
        }
        
        QPushButton {
            background-color: #4a4a4a;
            color: #ffffff;
            border: 1px solid #666666;
            border-radius: 6px;
            padding: 8px 16px;
            font-weight: bold;
        }
        
        QPushButton:hover {
            background-color: #5a5a5a;
            border-color: #777777;
        }
        
        QPushButton:pressed {
            background-color: #3a3a3a;
        }
        
        QPushButton:disabled {
            background-color: #2a2a2a;
            color: #666666;
            border-color: #444444;
        }
        
        QPushButton#recordButton {
            background-color: #c41e3a;
            border-color: #d63447;
            min-height: 40px;
            font-size: 14px;
        }
        
        QPushButton#recordButton:hover {
            background-color: #d63447;
        }
        
        QPushButton#recordButton:pressed {
            background-color: #a01729;
        }
        
        QComboBox {
            background-color: #4a4a4a;
            border: 1px solid #666666;
            border-radius: 4px;
            padding: 6px;
            color: #ffffff;
        }
        
        QComboBox:hover {
            border-color: #777777;
        }
        
        QComboBox::drop-down {
            border: none;
            width: 20px;
        }
        
        QComboBox::down-arrow {
            image: none;
            border-left: 4px solid transparent;
            border-right: 4px solid transparent;
            border-top: 6px solid #ffffff;
        }
        
        QComboBox QAbstractItemView {
            background-color: #4a4a4a;
            border: 1px solid #666666;
            selection-background-color: #0078d4;
        }
        
        QLabel {
            color: #ffffff;
            background: transparent;
        }
        
        QLabel#statusLabel {
            color: #90ee90;
            font-weight: bold;
        }
        
        QLabel#timerLabel {
            font-size: 24px;
            font-weight: bold;
            color: #ffffff;
        }
        
        QListWidget {
            background-color: #3c3c3c;
            border: 1px solid #555555;
            border-radius: 4px;
            alternate-background-color: #444444;
        }
        
        QListWidget::item {
            padding: 8px;
            border-bottom: 1px solid #555555;
        }
        
        QListWidget::item:selected {
            background-color: #0078d4;
        }
        
        QListWidget::item:hover {
            background-color: #505050;
        }
        
        QProgressBar {
            border: 1px solid #555555;
            border-radius: 4px;
            text-align: center;
            background-color: #3c3c3c;
        }
        
        QProgressBar::chunk {
            background-color: #0078d4;
            border-radius: 3px;
        }
        
        QMenuBar {
            background-color: #2b2b2b;
            color: #ffffff;
            border-bottom: 1px solid #555555;
        }
        
        QMenuBar::item {
            padding: 4px 8px;
        }
        
        QMenuBar::item:selected {
            background-color: #0078d4;
        }
        
        QMenu {
            background-color: #3c3c3c;
            border: 1px solid #555555;
        }
        
        QMenu::item {
            padding: 6px 20px;
        }
        
        QMenu::item:selected {
            background-color: #0078d4;
        }
        
        QScrollBar:vertical {
            background-color: #3c3c3c;
            width: 12px;
            border-radius: 6px;
        }
        
        QScrollBar::handle:vertical {
            background-color: #606060;
            border-radius: 6px;
            min-height: 20px;
        }
        
        QScrollBar::handle:vertical:hover {
            background-color: #707070;
        }
        """
    
    def _get_light_theme_css(self) -> str:
        """Get light theme CSS"""
        return """
        QWidget {
            background-color: #ffffff;
            color: #000000;
            font-family: 'Segoe UI', Arial, sans-serif;
        }
        
        QMainWindow {
            background-color: #ffffff;
        }
        
        QFrame {
            background-color: #f0f0f0;
            border: 1px solid #cccccc;
            border-radius: 4px;
        }
        
        QPushButton {
            background-color: #e6e6e6;
            color: #000000;
            border: 1px solid #cccccc;
            border-radius: 6px;
            padding: 8px 16px;
            font-weight: bold;
        }
        
        QPushButton:hover {
            background-color: #d6d6d6;
            border-color: #aaaaaa;
        }
        
        QPushButton:pressed {
            background-color: #c6c6c6;
        }
        
        QPushButton:disabled {
            background-color: #f0f0f0;
            color: #888888;
            border-color: #dddddd;
        }
        
        QPushButton#recordButton {
            background-color: #dc3545;
            color: #ffffff;
            border-color: #dc3545;
            min-height: 40px;
            font-size: 14px;
        }
        
        QPushButton#recordButton:hover {
            background-color: #c82333;
        }
        
        QPushButton#recordButton:pressed {
            background-color: #bd2130;
        }
        
        QComboBox {
            background-color: #ffffff;
            border: 1px solid #cccccc;
            border-radius: 4px;
            padding: 6px;
            color: #000000;
        }
        
        QComboBox:hover {
            border-color: #aaaaaa;
        }
        
        QComboBox::drop-down {
            border: none;
            width: 20px;
        }
        
        QComboBox::down-arrow {
            image: none;
            border-left: 4px solid transparent;
            border-right: 4px solid transparent;
            border-top: 6px solid #000000;
        }
        
        QComboBox QAbstractItemView {
            background-color: #ffffff;
            border: 1px solid #cccccc;
            selection-background-color: #007acc;
        }
        
        QLabel {
            color: #000000;
            background: transparent;
        }
        
        QLabel#statusLabel {
            color: #28a745;
            font-weight: bold;
        }
        
        QLabel#timerLabel {
            font-size: 24px;
            font-weight: bold;
            color: #000000;
        }
        
        QListWidget {
            background-color: #ffffff;
            border: 1px solid #cccccc;
            border-radius: 4px;
            alternate-background-color: #f8f9fa;
        }
        
        QListWidget::item {
            padding: 8px;
            border-bottom: 1px solid #eeeeee;
        }
        
        QListWidget::item:selected {
            background-color: #007acc;
            color: #ffffff;
        }
        
        QListWidget::item:hover {
            background-color: #e9ecef;
        }
        
        QProgressBar {
            border: 1px solid #cccccc;
            border-radius: 4px;
            text-align: center;
            background-color: #f8f9fa;
        }
        
        QProgressBar::chunk {
            background-color: #007acc;
            border-radius: 3px;
        }
        
        QMenuBar {
            background-color: #ffffff;
            color: #000000;
            border-bottom: 1px solid #cccccc;
        }
        
        QMenuBar::item {
            padding: 4px 8px;
        }
        
        QMenuBar::item:selected {
            background-color: #007acc;
            color: #ffffff;
        }
        
        QMenu {
            background-color: #ffffff;
            border: 1px solid #cccccc;
        }
        
        QMenu::item {
            padding: 6px 20px;
        }
        
        QMenu::item:selected {
            background-color: #007acc;
            color: #ffffff;
        }
        
        QScrollBar:vertical {
            background-color: #f0f0f0;
            width: 12px;
            border-radius: 6px;
        }
        
        QScrollBar::handle:vertical {
            background-color: #cccccc;
            border-radius: 6px;
            min-height: 20px;
        }
        
        QScrollBar::handle:vertical:hover {
            background-color: #aaaaaa;
        }
        """
    
    def get_current_theme(self) -> str:
        """Get current theme name"""
        return self.current_theme
    
    def toggle_theme(self, app: QApplication) -> str:
        """Toggle between dark and light themes"""
        new_theme = "light" if self.current_theme == "dark" else "dark"
        self.apply_theme(app, new_theme)
        return new_theme