#!/usr/bin/env python3
"""Extract local CSS token data as JSON; never execute or fetch CSS content."""
import argparse
import json
from pathlib import Path
import re
import sys

COLOR_PATTERNS = (
    r'#[0-9a-fA-F]{6}\b',
    r'#[0-9a-fA-F]{3}\b',
    r'rgb\(\s*\d+\s*,\s*\d+\s*,\s*\d+\s*\)',
    r'hsl\(\s*\d+\s*,\s*[\d.]+%\s*,\s*[\d.]+%\s*\)',
)
FONT_PATTERN = r'font-family\s*:\s*[\'\"]?([^,;\'\"{}]+)[\'\"]?'
SKIP_FONTS = {'inherit', 'initial', 'unset', 'sans-serif', 'serif', 'monospace',
              'cursive', 'fantasy', 'system-ui', '-apple-system', 'blinkmacsystemfont',
              'segoe ui', 'roboto', 'helvetica neue', 'arial', 'times new roman'}


def extract(export):
    if export.is_symlink() or not export.is_dir():
        raise ValueError('Use a regular local CSS export directory')
    colors, fonts = set(), set()
    for path in sorted(export.rglob('*.css')):
        if path.is_symlink():
            raise ValueError('CSS input contains a symbolic link')
        css = path.read_text(errors='ignore')
        for pattern in COLOR_PATTERNS:
            colors.update(re.findall(pattern, css, re.IGNORECASE))
        for match in re.finditer(FONT_PATTERN, css, re.IGNORECASE):
            font = match.group(1).strip().strip("'\"").strip()
            if font and font.lower() not in SKIP_FONTS and len(font) > 2:
                fonts.add(font)
    return {'colors': sorted(colors)[:12], 'fonts': sorted(fonts)[:4]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('export', type=Path)
    args = parser.parse_args()
    try:
        result = extract(args.export)
    except (OSError, ValueError) as error:
        print('[Build] CSS token extraction failed: ' + str(error), file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
