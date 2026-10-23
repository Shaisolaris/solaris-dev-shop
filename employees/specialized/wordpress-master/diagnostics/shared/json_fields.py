#!/usr/bin/env python3
"""Read named WordPress diagnostic JSON fields from stdin; never evaluate input.

Run this bundled script with python3 -I so project files cannot shadow its
standard-library imports. Exit 0 means the requested field was read/matched;
1 means invalid data or a slug mismatch; 2 means invalid command arguments.
"""
import argparse
import json
import re
import sys

MAX_INPUT_BYTES = 1024 * 1024
FIELDS = (
    "plugin-matches", "build-id", "theme-slug", "creation-mode", "modification-count",
    "robots-allowed", "scrape-success", "scrape-error",
)


def read_field(field, data, expected_slug=None):
    if not isinstance(data, dict):
        raise ValueError("expected a JSON object")
    if field == "plugin-matches":
        if data.get("slug") != expected_slug:
            raise ValueError("plugin slug was not confirmed")
        return None
    if field == "build-id":
        value = data.get("build_id", "")
    elif field == "theme-slug":
        theme = data.get("theme", {})
        if not isinstance(theme, dict):
            raise ValueError("theme must be an object")
        value = theme.get("slug", "")
    elif field == "creation-mode":
        value = data.get("creation_mode", data.get("mode", ""))
    elif field == "modification-count":
        modifications = data.get("modifications", [])
        if not isinstance(modifications, list):
            raise ValueError("modifications must be an array")
        return str(len(modifications))
    elif field in ("robots-allowed", "scrape-success"):
        value = data.get("allowed" if field == "robots-allowed" else "success")
        if type(value) is not bool:
            raise ValueError("expected a boolean status")
        return "true" if value else "false"
    else:
        value = data.get("error", "Unknown scrape error")
    if not isinstance(value, str):
        raise ValueError("expected a string field")
    return value


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("field", choices=FIELDS)
    parser.add_argument("--expected-slug")
    args = parser.parse_args(argv)
    if args.field == "plugin-matches":
        if not args.expected_slug or not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", args.expected_slug):
            parser.error("plugin-matches requires a lowercase --expected-slug")
    elif args.expected_slug is not None:
        parser.error("--expected-slug is only valid for plugin-matches")
    try:
        raw = sys.stdin.buffer.read(MAX_INPUT_BYTES + 1)
        if len(raw) > MAX_INPUT_BYTES:
            raise ValueError("JSON input exceeds 1 MiB")
        result = read_field(args.field, json.loads(raw.decode("utf-8")), args.expected_slug)
    except (UnicodeError, ValueError, RecursionError):
        # Do not copy malformed/untrusted input into diagnostics.
        print("Invalid diagnostic JSON or unconfirmed field", file=sys.stderr)
        return 1
    if result is not None:
        print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
