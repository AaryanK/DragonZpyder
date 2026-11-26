import struct
import tempfile
import unittest
import zipfile
from pathlib import Path

from check_native_alignment import inspect, load_segments


def synthetic_elf(alignment, offset=0, vaddr=0):
    ident=b"\x7fELF"+bytes([2,1,1])+bytes(9)
    header=struct.pack("<16sHHIQQQIHHHHHH",ident,3,183,1,0,64,0,0,64,56,1,0,0,0)
    segment=struct.pack("<IIQQQQQQ",1,5,offset,vaddr,0,0,0,alignment)
    return header+segment


class NativeAlignmentTest(unittest.TestCase):
    def test_segments(self):
        self.assertTrue(load_segments(synthetic_elf(16384))[1][0]["aligned"])
        self.assertTrue(load_segments(synthetic_elf(65536))[1][0]["aligned"])
        self.assertFalse(load_segments(synthetic_elf(4096))[1][0]["aligned"])
        self.assertFalse(load_segments(synthetic_elf(16384,0,4096))[1][0]["aligned"])
        with self.assertRaises(ValueError):
            load_segments(b"invalid")

    def test_archive(self):
        with tempfile.TemporaryDirectory() as root:
            path=Path(root)/"test.apk"
            with zipfile.ZipFile(path,"w") as z:
                z.writestr("lib/arm64-v8a/good.so",synthetic_elf(16384))
                z.writestr("lib/arm64-v8a/bad.so",synthetic_elf(4096))
                z.writestr("assets/not_a_library.so",b"ignored")
            result=inspect(path)
            self.assertFalse(result["passed"])
            self.assertEqual(len(result["libraries"]),2)


if __name__ == "__main__":
    unittest.main()
