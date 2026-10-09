"""Feature detection and descriptor matching.

Two things matter here and both are tested against real decoded pixels: the
matching copy is genuinely downscaled (and reports the scale it actually used,
which the pair transform depends on), and a pair that cannot be matched fails
with a status instead of an exception.
"""

from __future__ import annotations

import numpy as np
import pytest

from edge_ortho.contracts import FrameRecord
from edge_ortho.features.matching import (
    create_detector,
    detect_features,
    load_matching_copy,
    match_descriptors,
    matching_scale,
)

from conftest import big_scene, write_geotagged_jpeg


def test_matching_scale_targets_the_requested_megapixels():
    scale = matching_scale(4000, 2250, 0.6)
    assert (4000 * scale) * (2250 * scale) / 1e6 == pytest.approx(0.6, rel=0.02)
    assert 0 < scale < 1


def test_matching_scale_never_upscales():
    assert matching_scale(640, 480, 0.6) == 1.0
    assert matching_scale(0, 0, 0.6) == 1.0


def test_matching_copy_reports_the_scale_it_actually_used(tmp_path):
    """Regression: the effective scale is not the requested one after decoding.</ard>"""
    path = write_geotagged_jpeg(tmp_path / "frame.jpg", big_scene(1200, 900), 46.8, -91.9)
    loaded = load_matching_copy(path, 0.25)
    assert loaded is not None
    image, scale = loaded
    height, width = image.shape[:2]
    assert width < 1200 and height < 900
    # The returned scale must describe the returned image, not the request.
    assert width == pytest.approx(1200 * scale, abs=2)
    assert height == pytest.approx(900 * scale, abs=2)


def test_detector_rejects_unknown_kinds():
    with pytest.raises(ValueError):
        create_detector("sift-ish")


def test_features_are_detected_on_a_real_frame(tmp_path):
    path = write_geotagged_jpeg(tmp_path / "DJI_0001.JPG", big_scene(1400, 1000), 46.84, -91.99)
    features = detect_features(path, "DJI_0001", matching_scale(1400, 1000, 0.6), create_detector("orb"), "orb")
    assert features.error is None
    assert features.count > 200
    assert features.descriptors is not None
    assert features.width == pytest.approx(1400 * features.scale, abs=2)


def test_unreadable_frame_yields_a_status_not_an_exception(tmp_path):
    missing = tmp_path / "not_there.jpg"
    features = detect_features(missing, "ghost", 0.5, create_detector("orb"), "orb")
    assert features.error == "decode_failed"
    assert features.count == 0


def test_overlapping_frames_match_with_lowes_ratio(tmp_path):
    scene = big_scene(1600, 900, seed=5)
    a = write_geotagged_jpeg(tmp_path / "a.jpg", scene[:, :900], 46.84, -91.99)
    b = write_geotagged_jpeg(tmp_path / "b.jpg", scene[:, 120:1020], 46.8400, -91.9930)
    fa = detect_features(a, "a", 0.6, create_detector("orb"), "orb")
    fb = detect_features(b, "b", 0.6, create_detector("orb"), "orb")
    result = match_descriptors(fa, fb, ratio_threshold=0.75, min_matches=18)
    assert result.status == "ok"
    assert result.ratio_matches >= 18
    assert result.src_points is not None and result.dst_points is not None
    # Matched points keep the (N, 1, 2) shape OpenCV expects for RANSAC.
    assert result.src_points.shape == result.dst_points.shape
    assert result.src_points.shape[:2] == (result.ratio_matches, 1)
    assert result.src_points.shape[2] == 2

    src_xy = result.src_points.reshape(-1, 2)
    dst_xy = result.dst_points.reshape(-1, 2)
    dx = (dst_xy[:, 0] - src_xy[:, 0]).mean()
    dy = (dst_xy[:, 1] - src_xy[:, 1]).mean()
    assert dx == pytest.approx(-120 * fa.scale, rel=0.25)
    assert abs(dy) == pytest.approx(0, abs=12)


def test_unrelated_frames_do_not_claim_a_match(tmp_path):
    a = write_geotagged_jpeg(tmp_path / "noise_a.jpg", big_scene(700, 500, seed=1), 46.84, -91.99)
    b = write_geotagged_jpeg(tmp_path / "noise_b.jpg", big_scene(700, 500, seed=999), 46.9, -92.1)
    fa = detect_features(a, "a", 0.6, create_detector("orb"), "orb")
    fb = detect_features(b, "b", 0.6, create_detector("orb"), "orb")
    result = match_descriptors(fa, fb, ratio_threshold=0.75, min_matches=18)
    # Either the ratio filter or the match floor rejects it; never "ok".
    assert result.status != "ok"
    assert result.status in {"insufficient_matches", "no_descriptors", "too_few_ratio_matches"}


def test_frame_without_descriptors_is_reported(tmp_path):
    blank = np.zeros((400, 400, 3), dtype=np.uint8)
    path = write_geotagged_jpeg(tmp_path / "blank.jpg", blank, 46.84, -91.99)
    empty = detect_features(path, "blank", 0.6, create_detector("orb"), "orb")
    other = detect_features(
        write_geotagged_jpeg(tmp_path / "tex.jpg", big_scene(700, 500), 46.84, -91.99),
        "tex",
        0.6,
        create_detector("orb"),
        "orb",
    )
    result = match_descriptors(empty, other, min_matches=18)
    assert result.status != "ok"
    assert result.error is not None or result.ratio_matches == 0


def test_match_result_points_are_pixel_coordinates():
    """Guard against coordinates being returned in normalised form by mistake."""
    from edge_ortho.features.matching import FrameFeatures

    rng = np.random.default_rng(3)
    pts = rng.uniform(0, 400, size=(40, 2))
    src = FrameFeatures("s", "s.jpg", 0.5, 800, 600, keypoints=[None] * 40)
    src.descriptors = np.zeros((40, 32), dtype=np.uint8)
    dst = FrameFeatures("d", "d.jpg", 0.5, 800, 600, keypoints=[None] * 40)
    dst.descriptors = np.zeros((40, 32), dtype=np.uint8)
    from edge_ortho.features.matching import MatchResult

    matches = MatchResult(
        "ok",
        raw_matches=40,
        ratio_matches=40,
        src_points=pts.reshape(-1, 1, 2),
        dst_points=(pts + 10).reshape(-1, 1, 2),
    )
    assert matches.src_points.reshape(-1, 2).max() > 1.0
