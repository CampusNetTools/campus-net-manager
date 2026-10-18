import os
import struct
import tempfile
import unittest
import zlib

from scripts.check_android_screenshot import _png_rgba


def _write_png(path, color):
    width, height = 30, 30
    raw = b"".join(b"\x00" + bytes(color) * width for _ in range(height))

    def chunk(kind, payload):
        return (struct.pack(">I", len(payload)) + kind + payload
                + struct.pack(">I", zlib.crc32(kind + payload) & 0xffffffff))

    image = (b"\x89PNG\r\n\x1a\n"
             + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
             + chunk(b"IDAT", zlib.compress(raw))
             + chunk(b"IEND", b""))
    with open(path, "wb") as stream:
        stream.write(image)


class AndroidScreenshotTests(unittest.TestCase):
    def test_blank_app_content_is_not_accepted(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "black.png")
            _write_png(path, (0, 0, 0, 255))
            width, height, visible, sampled = _png_rgba(path)
        self.assertEqual((width, height), (30, 30))
        self.assertEqual(visible, 0)
        self.assertGreater(sampled, 0)

    def test_colored_app_content_is_detected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "visible.png")
            _write_png(path, (40, 120, 220, 255))
            _, _, visible, sampled = _png_rgba(path)
        self.assertEqual(visible, sampled)


if __name__ == "__main__":
    unittest.main()
