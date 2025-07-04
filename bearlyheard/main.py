#!/usr/bin/env python3
"""
BearlyHeard - Main application entry point
"""

import sys
import logging
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt

from .gui import MainWindow, ThemeManager
from .utils import setup_logger, Config


def main():
    """Main application entry point"""
    # Set up logging
    logger = setup_logger()
    logger.info("Starting BearlyHeard application")
    
    # Load configuration
    config = Config()
    
    # Create Qt application (high DPI scaling is enabled by default in Qt6)
    from PyQt6.QtCore import Qt
    from PyQt6.QtGui import QGuiApplication
    
    app = QApplication(sys.argv)
    app.setApplicationName("BearlyHeard")
    app.setOrganizationName("BearlyHeard")
    
    # Apply theme
    theme_manager = ThemeManager()
    theme_manager.apply_theme(app, config.get("theme", "dark"))
    
    # Create and show main window
    window = MainWindow()
    window.show()
    
    # Run application
    logger.info("Application started successfully")
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
