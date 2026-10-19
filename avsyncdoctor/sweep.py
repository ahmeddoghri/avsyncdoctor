"""How accurate is the fit when the detected events are not perfect?

The bundled fixture has five exactly-placed anchors and recovers the offset
and drift to the digit. Real flash and click detection lands a frame or two
off. This draws random offsets and drifts, jitters every detected event, and
reports how far the recovered values land from the truth.

    python -m avsyncdoctor.sweep
"""
from __future__ import annotations

import json
import random
import statistics

from .core import analyze


def _case(rng: random.Random, anchors: int, jitter_ms: float) -> dict:
    offset = rng.uniform(-0.400, 0.400)
    ratio = 1 + rng.uniform(-0.008, 0.008)
    video_events, audio_events = [], []
    clock = 1.0
    for _ in range(anchors):
        clock += rng.uniform(1.5, 3.0)
        video = round(clock, 4)
        video_events.append(video)
        audio_events.append(round(video * ratio + offset + rng.gauss(0, jitter_ms / 1000), 6))
    report = analyze({
        "video_events_seconds": video_events,
        "audio_events_seconds": audio_events,
        "tolerance_ms": 40,
    })
    return {
        "offset_error_ms": abs(report["offset_ms"] - offset * 1000),
        "drift_error_ppm": abs(report["drift_ppm"] - (ratio - 1) * 1e6),
        "residual_ms": report["max_skew_after_model_ms"],
        "rmse_ms": report["fit_rmse_ms"],
        "passed_after_model": report["passed_after_model"],
    }


def run(trials: int = 200, anchors: int = 5, jitter_ms: float = 0.0, seed: int = 0) -> dict:
    rng = random.Random(seed)
    rows = [_case(rng, anchors, jitter_ms) for _ in range(trials)]
    return {
        "trials": trials,
        "anchors": anchors,
        "event_jitter_ms": jitter_ms,
        "median_offset_error_ms": round(statistics.median(r["offset_error_ms"] for r in rows), 3),
        "p95_offset_error_ms": round(sorted(r["offset_error_ms"] for r in rows)[int(trials * 0.95)], 3),
        "median_drift_error_ppm": round(statistics.median(r["drift_error_ppm"] for r in rows), 1),
        "median_max_residual_ms": round(statistics.median(r["residual_ms"] for r in rows), 3),
        "median_fit_rmse_ms": round(statistics.median(r["rmse_ms"] for r in rows), 3),
        "share_within_40ms_after_fit": round(sum(r["passed_after_model"] for r in rows) / trials, 3),
    }


def main() -> None:
    print(json.dumps({
        "exact_events": run(),
        "one_frame_jitter_24fps": run(jitter_ms=41.7, seed=3),
        "one_frame_jitter_more_anchors": run(anchors=12, jitter_ms=41.7, seed=5),
    }, indent=2))


if __name__ == "__main__":
    main()
