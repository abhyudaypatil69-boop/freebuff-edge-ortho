"""Shared fixtures for the EdgeOrtho test suite.

The tests build their own imagery. Nothing here depends on a dataset being
downloaded, so the suite runs offline, and every synthetic frame is written with
real EXIF/XMP tags so the metadata reader is exercised rather than mocked.
"""

from __future__ import annotations

import struct
from pathlib import Path

import numpy as np
import pytest

from edge_ortho import config


# --------------------------------------------------------------------------
# synthetic imagery
# --------------------------------------------------------------------------

def _texture(width: int, height: int, seed: int) -> np.ndarray:
    """A deterministic, richly textured RGB image.

    Random per-pixel noise is a poor stand-in for imagery: it has no repeatable
    structure at more than one scale, so feature matching behaves unrealistically.
    Blobs, edges and noise together give ORB something comparable to real ground.
    """
    rng = np.random.default_rng(seed)
    base = rng.integers(0, 255, size=(height // 8, width // 8, 3), dtype=np.uint8)
    import cv2

    smooth = cv2.resize(base, (width, height), interpolation=cv2.INTER_LINEAR)
    for _ in range(60):
        cx, cy = rng.integers(0, width), rng.integers(0, height)
        r = int(rng.integers(6, 28))
        colour = tuple(int(c) for c in rng.integers(0, 255, size=3))
        cv2.circle(smooth, (int(cx), int(cy)), r, colour, thickness=-1)
    for _ in range(40):
        x1, y1 = rng.integers(0, width), rng.integers(0, height)
        x2, y2 = x1 + int(rng.integers(-90, 90)), y1 + int(rng.integers(-90, 90))
        colour = tuple(int(c) for c in rng.integers(0, 255, size=3))
        cv2.line(smooth, (int(x1), int(y1)), (int(x2), int(y2)), colour, thickness=2)
    noise = rng.integers(-14, 14, size=smooth.shape, dtype=np.int16)
    return np.clip(smooth.astype(np.int16) + noise, 0, 255).astype(np.uint8)


def big_scene(width: int = 2200, height: int = 1100, seed: int = 7) -> np.ndarray:
    return _texture(width, height, seed)


# --------------------------------------------------------------------------
# EXIF / XMP writing
# --------------------------------------------------------------------------

def _dms(value: float) -> tuple[tuple[int, int], tuple[int, int], tuple[int, int]]:
    degrees = int(abs(value))
    minutes_float = (abs(value) - degrees) * 60
    minutes = int(minutes_float)
    seconds = (minutes_float - minutes) * 60
    return ((degrees, 1), (minutes, 1), (int(round(seconds * 1000)), 1000))


def write_geotagged_jpeg(
    path: Path,
    image: np.ndarray,
    lat: float,
    lon: float,
    altitude_m: float | None = 90.0,
    yaw_deg: float | None = None,
    focal_length_mm: float | None = 4.5,
    focal_length_35mm: int | None = 26,
    make: str = "DJI",
    model: str = "FC300S",
    xmp_relative_altitude: float | None = None,
    xmp_gimbal_yaw: float | None = None,
    quality: int = 88,
) -> Path:
    """Write an RGB array as a JPEG carrying GPS EXIF and, optionally, DJI XMP."""
    import cv2
    import piexif

    path.parent.mkdir(parents=True, exist_ok=True)
    ok, buf = cv2.imencode(".jpg", image[:, :, ::-1], [int(cv2.IMWRITE_JPEG_QUALITY), quality])
    assert ok, "JPEG encoding failed"
    jpeg = buf.tobytes()

    if xmp_relative_altitude is not None or xmp_gimbal_yaw is not None:
        jpeg = _inject_xmp(
            jpeg,
            xmp_relative_altitude=xmp_relative_altitude,
            xmp_gimbal_yaw=xmp_gimbal_yaw,
            xmp_absolute_altitude=altitude_m,
            lat=lat,
            lon=lon,
        )

    zeroth = {
        piexif.ImageIFD.Make: make.encode(),
        piexif.ImageIFD.Model: model.encode(),
        piexif.ImageIFD.Software: b"EdgeOrtho tests",
    }
    exif: dict = {piexif.ExifIFD.DateTimeOriginal: b"2026:02:11 09:15:00"}
    if focal_length_mm is not None:
        exif[piexif.ExifIFD.FocalLength] = (int(focal_length_mm * 1000), 1000)
    if focal_length_35mm is not None:
        exif[piexif.ExifIFD.FocalLengthIn35mmFilm] = int(focal_length_35mm)

    gps: dict = {
        piexif.GPSIFD.GPSLatitudeRef: b"N" if lat >= 0 else b"S",
        piexif.GPSIFD.GPSLatitude: _dms(lat),
        piexif.GPSIFD.GPSLongitudeRef: b"E" if lon >= 0 else b"W",
        piexif.GPSIFD.GPSLongitude: _dms(lon),
    }
    if altitude_m is not None:
        gps[piexif.GPSIFD.GPSAltitudeRef] = 0 if altitude_m >= 0 else 1
        gps[piexif.GPSIFD.GPSAltitude] = (int(abs(altitude_m) * 1000), 1000)
    if yaw_deg is not None:
        gps[piexif.GPSIFD.GPSImgDirectionRef] = b"T"
        gps[piexif.GPSIFD.GPSImgDirection] = (int(yaw_deg * 1000), 1000)

    path.write_bytes(jpeg)
    exif_bytes = piexif.dump({"0th": zeroth, "Exif": exif, "GPS": gps})
    piexif.insert(exif_bytes, str(path))
    return path


def _inject_xmp(
    jpeg: bytes,
    *,
    xmp_relative_altitude: float | None,
    xmp_gimbal_yaw: float | None,
    xmp_absolute_altitude: float | None,
    lat: float,
    lon: float,
) -> bytes:
    """Insert a DJI-style XMP APP1 segment directly after the SOI marker.

    Writing the packet by hand keeps the test independent of any XMP library and
    matches how the reader scans the file head for ``<x:xmpmeta``.
    """
    attrs = [
        'xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"',
        'xmlns:drone-dji="http://www.dji.com/drone-dji/1.0/"',
        'xmlns:exif="http://ns.adobe.com/exif/1.0/"',
    ]
    body = [
        "<x:xmpmeta " + " ".join(attrs) + ">",
        "<rdf:RDF><rdf:Description rdf:about=\"\"",
    ]
    if xmp_relative_altitude is not None:
        body.append(f'drone-dji:RelativeAltitude="{xmp_relative_altitude:+.2f}"')
    if xmp_absolute_altitude is not None:
        body.append(f'drone-dji:AbsoluteAltitude="{xmp_absolute_altitude:+.2f}"')
    if xmp_gimbal_yaw is not None:
        body.append(f'drone-dji:GimbalYawDegree="{xmp_gimbal_yaw:+.2f}"')
        body.append('drone-dji:GimbalPitchDegree="-90.00"')
    body.append(f'exif:GPSLatitude="{lat:.8f}"')
    body.append(f'exif:GPSLongitude="{lon:.8f}"')
    body.append("/></rdf:RDF></x:xmpmeta>")
    xmp = "".join(body).encode("utf-8")

    payload = b"http://ns.adobe.com/xap/1.0/\x00" + xmp
    segment = b"\xff\xe1" + struct.pack(">H", len(payload) + 2) + payload
    assert jpeg[:2] == b"\xff\xd8"
    return jpeg[:2] + segment + jpeg[2:]


def write_plain_jpeg(path: Path, image: np.ndarray) -> Path:
    """A JPEG with no EXIF at all - used for the missing-GPS path."""
    import cv2

    path.parent.mkdir(parents=True, exist_ok=True)
    ok, buf = cv2.imencode(".jpg", image[:, :, ::-1], [int(cv2.IMWRITE_JPEG_QUALITY), 85])
    assert ok
    path.write_bytes(buf.tobytes())
    return path


# --------------------------------------------------------------------------
# fixtures
# --------------------------------------------------------------------------

@pytest.fixture()
def scene() -> np.ndarray:
    return big_scene()


@pytest.fixture()
def flight_folder(tmp_path: Path) -> Path:
    """Eight geotagged frames cut from one synthetic scene along a transect.

    Frames are 512x384 crops spaced 60 px apart, which is real overlap rather
    than a synthetic best case: 75% along-track overlap at ~0.02 m/px.
    """
    folder = tmp_path / "flight"
    folder.mkdir()
    scene_img = big_scene(width=1400, height=1200, seed=11)
    lat0, lon0 = 46.84270, -91.99380
    for i in range(8):
        x = 40 + i * 60
        y = 40
        crop = scene_img[y : y + 384, x : x + 512]
        # ~0.6 m per step north-east of the previous frame
        write_geotagged_jpeg(
            folder / f"DJI_{1000 + i}.JPG",
            crop,
            lat=lat0 + i * 0.0000055,
            lon=lon0 + i * 0.0000075,
            altitude_m=90.0 + i * 0.5,
            yaw_deg=90.0,
            xmp_relative_altitude=90.0 + i * 0.5,
            xmp_gimbal_yaw=90.0,
        )
    return folder


@pytest.fixture(autouse=True)
def isolated_workspace(tmp_path_factory, monkeypatch):
    """Keep every test's outputs out of the real data/ and outputs/ folders.

    Modules bind these paths at import time (``from .config import DB_PATH``), so
    the rebound values are patched there too rather than trusting the config module.
    """
    from edge_ortho import sample as sample_module
    from edge_ortho import storage as storage_module

    root = tmp_path_factory.mktemp("edgeortho")
    data = root / "data"
    outputs = root / "outputs"
    data.mkdir()
    outputs.mkdir()
    paths = {
        "DATA_DIR": data,
        "RAW_DIR": data / "raw",
        "UPLOAD_DIR": data / "uploads",
        "META_DIR": data / "meta",
        "OUTPUT_DIR": outputs,
        "DB_PATH": data / "edgeortho.sqlite3",
    }
    for name, value in paths.items():
        monkeypatch.setattr(config, name, value, raising=False)
    monkeypatch.setattr(storage_module, "DB_PATH", paths["DB_PATH"], raising=False)
    monkeypatch.setattr(sample_module, "RAW_DIR", paths["RAW_DIR"], raising=False)
    config.ensure_dirs()
    yield root
