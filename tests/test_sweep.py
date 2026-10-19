import unittest

from avsyncdoctor.sweep import run


class SweepTest(unittest.TestCase):
    def test_exact_anchors_recover_offset_and_drift_essentially_perfectly(self):
        result = run(trials=60)
        self.assertLess(result["median_offset_error_ms"], 0.01)
        self.assertLess(result["median_drift_error_ppm"], 1.0)
        self.assertEqual(result["share_within_40ms_after_fit"], 1.0)

    def test_more_anchors_improve_the_fitted_parameters(self):
        few = run(trials=60, anchors=5, jitter_ms=41.7, seed=3)
        many = run(trials=60, anchors=12, jitter_ms=41.7, seed=3)
        self.assertLess(many["median_offset_error_ms"], few["median_offset_error_ms"])
        self.assertLess(many["median_drift_error_ppm"], few["median_drift_error_ppm"])

    def test_max_residual_inflates_with_anchor_count_while_rmse_does_not(self):
        # max_skew_after_model_ms is an order statistic over the anchors, so
        # it grows as anchors are added even though the fit gets better.
        # fit_rmse_ms stays near the anchor noise level, which is why it is
        # the number to gate on when anchors are detected rather than exact.
        few = run(trials=60, anchors=5, jitter_ms=41.7, seed=3)
        many = run(trials=60, anchors=12, jitter_ms=41.7, seed=3)
        self.assertGreater(many["median_max_residual_ms"], few["median_max_residual_ms"])
        self.assertLess(many["median_fit_rmse_ms"], 41.7 * 1.2)


if __name__ == "__main__":
    unittest.main()
