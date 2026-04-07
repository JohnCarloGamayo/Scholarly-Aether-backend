"""Test SVG to PNG conversion"""
import sys
sys.path.insert(0, '.')

from app.services.pdf import convert_svg_to_png

# Simple SVG test data
svg_data = b'''<?xml version="1.0" encoding="UTF-8"?>
<svg width="100" height="100" xmlns="http://www.w3.org/2000/svg">
  <circle cx="50" cy="50" r="40" fill="blue" />
  <text x="50" y="55" text-anchor="middle" fill="white" font-size="20">SVG</text>
</svg>'''

print("Testing SVG to PNG conversion...")
success = convert_svg_to_png(svg_data, "test_output.png", width=200)

if success:
    print("✓ SVG conversion successful!")
    print("✓ Output saved to: test_output.png")
    import os
    if os.path.exists("test_output.png"):
        size = os.path.getsize("test_output.png")
        print(f"✓ File size: {size} bytes")
else:
    print("✗ SVG conversion failed!")
    sys.exit(1)
