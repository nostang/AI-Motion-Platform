import unittest

from src.pipeline.dispatcher import MotionType, detect_motion_type


class MotionDispatcherTests(unittest.TestCase):
    def test_detects_supported_types(self):
        self.assertEqual(detect_motion_type("FW_001"), MotionType.FOOTWORK)
        self.assertEqual(detect_motion_type("SV_001"), MotionType.SERVE)
        self.assertEqual(detect_motion_type("CL_001"), MotionType.CLEAR)

    def test_rejects_unknown_prefix(self):
        with self.assertRaises(ValueError):
            detect_motion_type("XX_001")


if __name__ == "__main__":
    unittest.main()
