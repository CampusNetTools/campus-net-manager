#!/usr/bin/env python3
"""Reject Android emulator screenshots whose app content is still blank."""

import argparse
import struct
import sys
import zlib


def _png_rgba(path):
    with open(path, "rb") as stream:
        data = stream.read()
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("screenshot is not a PNG")

    offset = 8
    width = height = bit_depth = color_type = None
    compressed = bytearray()
    while offset + 12 <= len(data):
        length = struct.unpack_from(">I", data, offset)[0]
        kind = data[offset + 4:offset + 8]
        start = offset + 8
        end = start + length
        if end + 4 > len(data):
            raise ValueError("truncated PNG chunk")
        payload = data[start:end]
        if kind == b"IHDR":
            width, height, bit_depth, color_type, compression, filtering, interlace = struct.unpack(
                ">IIBBBBB", payload
            )
            if compression or filtering or interlace:
                raise ValueError("unsupported PNG encoding")
        elif kind == b"IDAT":
            compressed.extend(payload)
        elif kind == b"IEND":
            break
        offset = end + 4

    if bit_depth != 8 or color_type != 6 or width <= 0 or height <= 0:
        raise ValueError("expected an 8-bit RGBA Android screenshot")
    raw = zlib.decompress(compressed)
    row_bytes = width * 4
    if len(raw) != height * (row_bytes + 1):
        raise ValueError("unexpected PNG pixel data size")

    previous = bytearray(row_bytes)
    body_start, body_end = height // 10, height * 9 // 10
    sampled = visible = 0
    cursor = 0
    for y in range(height):
        filter_type = raw[cursor]
        scanline = bytearray(raw[cursor + 1:cursor + 1 + row_bytes])
        cursor += row_bytes + 1
        if filter_type == 1:
            for i in range(4, row_bytes):
                scanline[i] = (scanline[i] + scanline[i - 4]) & 0xff
        elif filter_type == 2:
            for i in range(row_bytes):
                scanline[i] = (scanline[i] + previous[i]) & 0xff
        elif filter_type == 3:
            for i in range(row_bytes):
                left = scanline[i - 4] if i >= 4 else 0
                scanline[i] = (scanline[i] + ((left + previous[i]) // 2)) & 0xff
        elif filter_type == 4:
            for i in range(row_bytes):
                left = scanline[i - 4] if i >= 4 else 0
                above = previous[i]
                upper_left = previous[i - 4] if i >= 4 else 0
                estimate = left + above - upper_left
                distances = (abs(estimate - left), abs(estimate - above), abs(estimate - upper_left))
                predictor = (left, above, upper_left)[distances.index(min(distances))]
                scanline[i] = (scanline[i] + predictor) & 0xff
        elif filter_type != 0:
            raise ValueError(f"unsupported PNG row filter {filter_type}")

        if body_start <= y < body_end:
            for x in range(0, width, 5):
                i = x * 4
                red, green, blue = scanline[i:i + 3]
                sampled += 1
                if max(red, green, blue) >= 48:
                    visible += 1
        previous = scanline

    return width, height, visible, sampled


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("screenshot")
    parser.add_argument("--minimum-visible-fraction", type=float, default=0.001)
    args = parser.parse_args(argv)
    try:
        width, height, visible, sampled = _png_rgba(args.screenshot)
    except (OSError, ValueError, zlib.error) as exc:
        print(f"Android screenshot check failed: {exc}", file=sys.stderr)
        return 2
    fraction = visible / sampled if sampled else 0
    print(
        f"Android screenshot content: {width}x{height}, "
        f"{fraction * 100:.3f}% sampled pixels visible"
    )
    if fraction < args.minimum_visible_fraction:
        print("Android app content appears blank; refusing to pass launch smoke.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
