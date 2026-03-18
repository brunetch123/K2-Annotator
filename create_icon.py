#!/usr/bin/env python3
"""
Create Windows icon file from K2Icon.png

This script converts the PNG icon to ICO format with multiple sizes
for proper Windows display at different resolutions.

Usage: python create_icon.py
Output: K2Icon.ico
"""

import sys

def create_icon():
    try:
        from PIL import Image
    except ImportError:
        print("ERROR: Pillow not installed.")
        print("Install with: pip install pillow")
        return False
    
    input_file = "K2Icon.png"
    output_file = "K2Icon.ico"
    
    try:
        # Open the PNG image
        img = Image.open(input_file)
        print(f"Loaded: {input_file} ({img.size[0]}x{img.size[1]})")
        
        # Define icon sizes (Windows uses these standard sizes)
        sizes = [
            (256, 256),  # Large
            (128, 128),  # Medium
            (64, 64),    # Small
            (48, 48),    # Explorer
            (32, 32),    # Taskbar
            (16, 16),    # Title bar
        ]
        
        # Convert to RGBA if needed
        if img.mode != 'RGBA':
            img = img.convert('RGBA')
        
        # Save as ICO with multiple sizes
        img.save(output_file, format='ICO', sizes=sizes)
        
        print(f"Created: {output_file}")
        print(f"Sizes included: {', '.join([f'{s[0]}x{s[1]}' for s in sizes])}")
        return True
        
    except FileNotFoundError:
        print(f"ERROR: {input_file} not found.")
        print("Make sure K2Icon.png is in the current directory.")
        return False
    except Exception as e:
        print(f"ERROR: {e}")
        return False

if __name__ == "__main__":
    success = create_icon()
    sys.exit(0 if success else 1)
