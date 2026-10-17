import os
import tempfile
import unittest
from pathlib import Path

from scripts.create_ikev2_device_profile import write_private


class IKEv2AppEnrollmentTests(unittest.TestCase):
    @unittest.skipUnless(hasattr(os, "fchmod"), "POSIX file modes are unavailable")
    def test_private_writer_restricts_permissions_on_existing_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "device.ikev2.json"
            path.write_bytes(b"old")
            path.chmod(0o644)
            write_private(path, b'{"password":"private"}')
            self.assertEqual(path.read_bytes(), b'{"password":"private"}')
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)


if __name__ == "__main__":
    unittest.main()
