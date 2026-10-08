import os
import tempfile
import unittest
from ed import saveio


class TestSave(unittest.TestCase):
    def test_roundtrip(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "save.json")
            st = saveio.load(p)
            self.assertEqual(st["unlocked"], 0)
            st["coins"] = 41
            st["abilities"] = ["dash"]
            saveio.save(st, p)
            st2 = saveio.load(p)
            self.assertEqual(st2["coins"], 41)
            self.assertEqual(st2["abilities"], ["dash"])

    def test_corrupt(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "save.json")
            with open(p, "w") as f:
                f.write("{not json")
            st = saveio.load(p)
            self.assertEqual(st["unlocked"], 0)


if __name__ == "__main__":
    unittest.main()
