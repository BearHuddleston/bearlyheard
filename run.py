#!/usr/bin/env python3
"""
BearlyHeard application launcher
"""

import sys
from pathlib import Path

# Add bearlyheard directory to Python path
src_path = Path(__file__).parent
sys.path.insert(0, str(src_path))

# Import and run main
from bearlyheard.main import main

if __name__ == "__main__":
    main()