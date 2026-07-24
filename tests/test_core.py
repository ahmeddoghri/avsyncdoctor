import tempfile
import unittest
from pathlib import Path

from avsyncdoctor.core import DEMO, analyze, analyze_media, correct_media, synthesize


class AVSyncDoctorTests(unittest.TestCase):
    def test_demo_recovers_offset_and_drift(self):
        result = analyze(DEMO)
        self.assertAlmostEqual(result["offset_ms"], 120, places=3)
        self.assertAlmostEqual(result["drift_ppm"], 5000, places=2)
        self.assertFalse(result["passed_before"])
        self.assertTrue(result["passed_after_model"])

    def test_requires_paired_events(self):
        with self.assertRaisesRegex(ValueError, "same length"):
            analyze({"video_events_seconds": [1, 2], "audio_events_seconds": [1]})

    def test_real_media_round_trip(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "drifted.mp4"
            corrected = Path(directory) / "corrected.mp4"
            synthesize(source)
            before = analyze_media(source)
            result = correct_media(source, corrected)
        self.assertGreater(before["max_skew_before_ms"], 100)
        self.assertLess(result["after"]["max_skew_before_ms"], 40)
        self.assertLess(abs(result["after"]["drift_ppm"]), 2500)


if __name__ == "__main__":
    unittest.main()
