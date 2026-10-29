#!/usr/bin/env python3
"""Update owned scrape artifacts using explicit data arguments, never code interpolation.

The CSS action removes textual content declarations with the original workflow's
pattern. It is not a general CSS security sanitizer. Invoke with python3 -I.
"""
import argparse
import json
from pathlib import Path
import re
import sys

CONTENT_DECLARATION = re.compile(r"""content\s*:\s*["']([^"'>{]+)["']""")


def update(action, path, status=None):
    if path.is_symlink() or not path.is_file():
        raise ValueError('the scrape artifact must be a regular non-symlink file')
    if action == 'css':
        source = path.read_text(encoding='utf-8', errors='ignore')
        result = CONTENT_DECLARATION.sub('content: ""', source)
        path.write_text(result, encoding='utf-8')
        return '[Build] CSS content: declarations sanitised'
    source = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(source, dict):
        raise ValueError('the scrape manifest must be a JSON object')
    source['robots_status'] = status
    path.write_text(json.dumps(source, indent=2), encoding='utf-8')
    return '[Build] scrape.json updated with robots_status=' + status


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('css', 'robots'))
    parser.add_argument('path', type=Path)
    parser.add_argument('status', nargs='?')
    args = parser.parse_args()
    if (args.action == 'robots') != (args.status is not None):
        parser.error('only the robots action requires one status argument')
    try:
        message = update(args.action, args.path, args.status)
    except (OSError, ValueError) as error:
        print('[Build] Scrape update failed: ' + str(error), file=sys.stderr)
        return 1
    print(message)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
