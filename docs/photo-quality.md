# Still-photo quality and gallery uploads — 2026-11-02

The previous photo path requested the same 1280x720 video stream as recording,
then saved a lossless PNG of that frame. Canvas already used intrinsic dimensions,
not CSS dimensions. The resolution request was the primary detail loss. Gallery
files were not recompressed. Server sanitization keeps decoded image dimensions,
applies EXIF orientation, strips metadata and writes lossless PNG. Feed img elements
use the full signed original with object-fit: contain; no thumbnail or resize stage
was found. Those backend/rendering settings do not need a quality increase.

Photo preview now requests flexible 1920x1080 independently of video. Supported
ImageCapture.takePhoto uses still capabilities bounded by existing 40Mpx/12000px
limits and retains the original encoded Blob. Unsupported photo settings retry
the camera default; unavailable/failing still capture uses one JPEG 0.95 encode at
actual videoWidth/videoHeight, never CSS dimensions or upscaling. Constraint-only
photo negotiation failures retry relaxed constraints; permission denial does not
prompt again. Existing 15 MiB image input, dimension and format guards remain.
Video constraints, codecs, duration, size, remux and scoring are unchanged.

Capture prominently offers Upload from gallery, with Photo/Video selection above
the preview. Existing selected bytes, previews, captions, progress, errors and
same-file/idempotency retry are preserved. Multipart extensions now match MIME.
Gallery remains zero points/no streak; capture photo=1 and video=3.

Verification: frontend lint/types/build and 30 unit tests passed. Backend Ruff,
format, mypy and 137 tests passed with no skips against real native PostgreSQL,
private MinIO and FFmpeg. Seven additional server tests show pixel-identical
decoded 1080p JPEG/PNG/WebP output after sanitization, including EXIF rotation
and metadata removal, and unchanged safety rejection.

All 11 real-backend browser tests passed. Three new browser cases verify native
stills and canvas fallback at 1920x1080, original aspect ratio, metadata-safe server
delivery, feed contain rendering, gallery photo/video previews/captions, progress,
lost-response same-key retry and gallery zero-point/no-streak rankings. They were
rerun after the final fallback allocation guard. On a deterministic fine-stripe
chart, per-channel mean absolute error was 59.36–59.37 for a 720p downsampled
baseline versus 0.00–0.01 for the new 1080p pipeline (0–255, lower is better).
The requested frame has 2.25 times the pixels of 720p. This synthetic comparison
does not establish optical/device-camera quality. Actual Android/iPhone native
still support, camera negotiation, focus/exposure and portrait behavior remain
physical-device checks in phone-checklist.md.

Test databases and MinIO data were isolated from production. The MinIO test data
directory lives outside the source tree. No production secrets/data/settings were
changed to run tests. Deployment uses the existing Render Free service.
