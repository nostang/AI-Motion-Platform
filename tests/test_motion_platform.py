import unittest
from pathlib import Path

from src.motion import MotionContext, get_motion_analyzer, registered_motion_types
from src.motion.analyzers import ClearAnalyzer, FootworkAnalyzer, ServeAnalyzer
from src.pipeline.dispatcher import MotionType, detect_motion_type


class MotionPlatformTests(unittest.TestCase):
    def test_registry_contains_completed_mvp_modules(self):
        self.assertEqual(registered_motion_types(), ("clear", "footwork", "serve"))
        self.assertIsInstance(get_motion_analyzer("footwork"), FootworkAnalyzer)
        self.assertIsInstance(get_motion_analyzer("serve"), ServeAnalyzer)
        self.assertIsInstance(get_motion_analyzer("clear"), ClearAnalyzer)

    def test_clear_motion_is_detected_by_dispatcher(self):
        self.assertEqual(detect_motion_type("CL_001"), MotionType.CLEAR)

    def test_unknown_motion_is_rejected_by_registry(self):
        with self.assertRaises(NotImplementedError):
            get_motion_analyzer("smash")

    def test_motion_context_preserves_input(self):
        context = MotionContext(
            video_id="SV_001",
            video_path=Path("SV_001.mov"),
            model_path=Path("pose.task"),
            window_name="Serve",
            display=False,
        )
        self.assertEqual(context.video_id, "SV_001")
        self.assertFalse(context.display)


if __name__ == "__main__":
    unittest.main()
