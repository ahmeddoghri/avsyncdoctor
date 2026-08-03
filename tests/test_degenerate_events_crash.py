import unittest

from avsyncdoctor.core import DEMO, analyze


class DegenerateEventsCrashTest(unittest.TestCase):
    """estimate() performed an unguarded least-squares fit. Identical
    video_events_seconds values made the variance denominator zero;
    perfectly constant audio_events_seconds made the fitted slope zero and
    the inverse-mapping division by that slope zero. Both raised an
    uncaught ZeroDivisionError -- not covered by server.py's exception
    tuple -- crashing the unauthenticated /api/analyze endpoint on
    realistic (not malicious) bad-fixture input."""

    def test_identical_video_timestamps_raises_clean_error(self):
        payload = {"video_events_seconds": [1.0, 1.0, 1.0], "audio_events_seconds": [1.1, 1.2, 1.3]}
        with self.assertRaises(ValueError):
            analyze(payload)

    def test_constant_audio_events_raises_clean_error(self):
        payload = {"video_events_seconds": [1.0, 2.0, 3.0], "audio_events_seconds": [5.0, 5.0, 5.0]}
        with self.assertRaises(ValueError):
            analyze(payload)

    def test_demo_output_unaffected(self):
        result = analyze(DEMO)
        self.assertAlmostEqual(result["offset_ms"], 120, places=3)
        self.assertAlmostEqual(result["drift_ppm"], 5000, places=2)
        self.assertFalse(result["passed_before"])
        self.assertTrue(result["passed_after_model"])


if __name__ == "__main__":
    unittest.main()
