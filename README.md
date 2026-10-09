# EdgeOrtho

**Local, edge-optimised 2D drone orthomosaic generation.**

EdgeOrtho turns a folder of overlapping, geotagged drone images into a
georeferenced 2D mosaic on the machine that holds the imagery. Nothing is
uploaded, and every run records the measurements it actually made: wall-clock
time, peak process RSS, disk and CPU usage, and per-stage timing. Unmeasured
values are returned as *unavailable* rather than filled in.

It is a first-round evaluation MVP built from the [GEOAI 01 project brief],
not a survey-grade production engine. It is explicitly **not claiming survey
accuracy without ground control**, and it is explicitly distinguishing a
preliminary visual mosaic from a validated geospatial output.

[GEOAI 01 project brief]: https://curo proto/GEOAI/GEOAI 01 — Edge Processing of High-Resolution Drone Imagery.pdf
(GEOAI 01) describes the constraints: low memory, limited CPU, reduced image
comparisons, privacy by default, and measurable performance.

## Quick start

From the project root (`edge-ortho/`):

```bash
# start the local backend (serves the API and the built UI)
cd backend
python -m edge_ortho.cli serve --host 127.0.0.1 --port 8000
```

Then open `http://127.0.0.1:8000`. If you want the frontend served through
Vite's dev server instead, run the frontend dev server in a second terminal
and leave the backend on port 8000 (the frontend dev server proxies `/api`
to the backend):

```bash
cd frontend
npm run dev     # serves on http://localhost:5173, proxies /api -> localhost:8000
```

The backend has a built-in UI path that serves the built frontend from
`frontend/dist`, so `python -m edge_ortho.cli serve` alone is enough for a
finished-app preview.

## First run

1. Start the backend.
2. Open the UI, or use the CLI.
3. Either drag-and-drop a folder in the browser, or run:

```bash
# inspect a local folder (zero upload; the backend reads it from disk)
cd backend
python -m edge_ortho.cli inspect /path/to/your/frames
```

or

```bash
# process a local folder end to end
cd backend
python -m edge_ortho.cli run /path/to/your/frames --name "my run"
```

4. On first use, the UI's sample dataset button downloads the **Brighton Beach**
   18-frame public dataset (BSD 2-Clause, Piero Toffanin) and records the
   licence and source. That dataset is the presence-of-function test for the
   product.

## What the product does

1. **Ingest** — discovers supported JPG/JPEG/TIFF files.
2. **Validate GPS** — reads EXIF/XMP GPS, altitude, focal length, camera model;
   rejects frames without usable GPS; projects to UTM; estimates GSD; builds the
   flight footprint.
3. **Plan neighbours** — uses GPS proximity to bound image comparisons instead of
   all-pairs, with an adaptive radius and overlap gating.
4. **Match features** — ORB (default) or AKAZE on downscaled copies, ratio-filtered
   brute-force matches, with status codes for bad pairs.
5. **Align** — solves a global similarity transform with a weak GPS prior and
   anchors the layout to the GPS track; optionally re-estimates pair transforms
   with a homography for comparison only.
6. **Compose tiles** — streams tiles to a windowed tessellated writer with a bounded
   decode cache and no full-canvas allocation.
7. **Georeference** — writes the CRS, transform, bounds; reopens to validate; produces
   (when available) a COG and XYZ web tiles and a mosaic preview.
8. **Export** — JSON report, CSV metrics, frame table, metadata report, tiles zip,
   preview PNG.

## First-round priority order

If time is short, this is the vertical slice priority the implementation followed:

1. Upload a small folder of real geotagged frames.
2. Validate and display GPS metadata.
3. Build the neighbour graph where GPS permits.
4. Match at least some image pairs and report real match/inlier statistics.
5. Generate the simplest defensible mosaic for a compatible small dataset.
6. Display a map or image preview.
7. Export the result and an actual metrics report.
8. Demonstrate a constrained resource profile if feasible.

## Design philosophy

- **Warm stone + deep forest-green**, restrained, map-inspired, GIS-redesigned,
  not AI-dashboard-generated. Typography: Inter/Geist. Sidebar and workspace.
- **Authentic map window** via Leaflet with real orthomosaic, footprints, and flight
  path overlays — never a random basemap claimed to be the result.
- **Honest loading, empty, and error states.** No fake progress, no invented
  resource values, no fabricated alignment quality.
- **Measured, not estimated.** RSS, CPU, disk, wall clock, throughput, bandwidth.
- **Privacy by default.** Raw imagery never leaves the machine.
- **Measured, not fabricated.** Unmeasured values render as "not measured", not
  as zero or blank.

## Architecture

See `docs/architecture.md` for the module map and stage-by-stage algorithm, and
`docs/README.briefing.md` for the honest measured-results summary and posture.

## Dependencies

Python backend: Python 3.11/3.12, FastAPI, OpenCV (headless), NumPy, SciPy,
pyproj, rasterio/GDAL, psutil, Pillow, piexif. Frontend: Node 18+, npm, Vite,
React/TypeScript, Tailwind CSS, Leaflet, Lucide icons.

For a fresh setup, install the Python deps first, then the Node deps:

```bash
cd backend
pip install -r requirements.txt   # (or your env manager)
cd ../frontend
npm install
```

## Tests

```bash
cd backend
pytest tests/            # the real pipeline, exercised on synthetic imagery
ruff check .             # lint (and `ruff check . --fix` where safe)
```

The test suite builds its own synthetic geotagged frames with real EXIF and XMP,
so it runs offline and exercises the real metadata reader, neighbour planner,
feature matcher, pair transform, composer, and raster writer.

## Sample dataset

The backend ships a sample-acquisition path for the **Brighton Beach** dataset.
It downloads the dataset, records the licence and source in
`data/raw/brighton_beach/DATASET_MANIFEST.json`, and lists the dataset in the
frontend's sample gallery. The raw imagery is not redistributed with the repo;
it lives in `data/raw/`, which is git-ignored.

See `docs/DATASET_GUIDE.md` for the license audit and dataset folder layout.

## Known limitations

- **No ground control.** No GCPs or check points, so absolute accuracy is not
  measured. The GPS-placement numbers are internal-consistency evidence.
- **Post-processed GPS.** DJI EXIF GPS comes from the drone's GNSS after
  processing, so the visual solution's agreement with those tags is a
  consistency check, not an independent validation.
- **Assumes near-nadir, planar RGB.** Tall structure, water, and steep terrain
  break the flat-ground assumption and will show parallax seams.
- **Homography comparison is evidence, not geometry.** Composition always uses
  the globally solved similarity model.
- **Constrained profiles are emulated on the host.** They demonstrate budget
  behaviour, not physical-device performance.
- **COG and XYZ tiles require the tooling.** If rasterio/GDAL do not expose the
  COG driver or tile rendering, those stages are reported as unavailable rather
  than silently skipped.
- **Brighton Beach is a small sample.** One 18-frame transect is not a general
  accuracy or performance claim.

## Demo script

`docs/demo_script.sh` is a reproducible shell script that exercises the product
through the API end to end: fetch the sample dataset, inspect it, run it once with
the defaults, run it a second time with the homography comparison enabled, and
validate the resulting GeoTIFF, COG, tiles, and performance records.

## What is implemented vs what is measured vs what is approximate

- **Implemented and real:** ingest, GPS validation, neighbour planning, ORB/AKAZE
  matching with ratio filtering, RANSAC pair transforms, global similarity
  alignment with GPS anchor and homography comparison, tile-stream composer,
  tiled GeoTIFF writer, COG conversion (when available), XYZ tiles (when
  available), mosaic preview, all eight stages, the API routes, the frontend
  pages, the SQLite run store, the performance ledger, and the bandwidth maths.
- **Measured on this machine:** the Brighton Beach runs reported in the briefing
  doc (wall clock, peak RSS, first tile, throughput, pairs, inliers, reprojection
  error, GPS-placement error, COG and tile sizes, bandwidth).
- **Approximate:** exposure compensation in the composer (per-frame median
  brightness over a downscaled sample), the neighbour radius (adaptive to measured
  footprint, not a magic constant), overlap estimation (only when footprint
  geometry is known), heading as a GPS-track fallback when no camera yaw tag exists,
  and the COG-stream memory measurement (done once on one raster).
