from vendor.parser.parse import parse


def main(rows):
    return [parse(r) for r in rows]
