# Validated 720p video remuxing — 2026-11-01

New uploads accept at most 720p: shorter encoded edge <=720px, longer <=1280px.
Landscape and portrait are allowed. Duration remains **5–30 seconds inclusive**,
input remains **50 MiB maximum**, camera video remains **3 points**, gallery remains
**0 points and no streak**. Existing stored videos are not modified or removed.
No database migration or public API field change is needed for this policy.

## Why processing changed

Previously every accepted H.264/VP8/VP9 input was decoded and encoded again with
libx264/AAC, padded to even dimensions and normalized to 30fps MP4. This stripped
metadata and unified playback, but spent substantial CPU even on compatible MP4.
Earlier 4K tests exceeded the free-hosting processing budget. The user approved
the new 720p acceptance limit; the server does not resize oversized input.

Now the pipeline is: bounded original-byte hashing → existing idempotent claim →
processing admission → forced local-only container probe → codec/layout/resolution
checks → full bounded decode/frame-CRC timing → decoded timing check → stream-copy remux →
output timing/size check → existing quota reservation/private PUT/atomic acceptance.
There is **no compressed video encoder or conversion fallback**. Decode validation is retained:
copying packets by itself cannot establish that compressed content is valid.

The first Ubuntu 24.04 CI run exposed that FFmpeg 6 progress reports can stop at
the last frame's presentation timestamp (4.9s for a valid 5s/10fps clip), while
newer versions include its duration. Validation now reads decoded frame-CRC
timestamps/durations with the source rational time base and passthrough timing,
including the last frame, instead of using progress. The exact 5–30s comparisons
remain unchanged. Checksums/timing stay internal and are never uploaded as logs.
[FFmpeg frame-CRC format](https://ffmpeg.org/ffmpeg-formats.html#framecrc).

| Input container | Accepted picture encoding | Optional audio | Output |
|---|---|---|---|
| ISO MP4 | H.264 Baseline, Constrained Baseline, Main or High; 8-bit yuv420p | AAC-LC | MP4, faststart |
| WebM | VP8 or VP9; 8-bit yuv420p | Opus or Vorbis | WebM |

Exactly one video and at most one audio stream; other stream layouts are rejected.
HEVC, 10-bit/HDR, unsupported profiles/codecs/container pairings, QuickTime/MOV and
generic Matroska are rejected. Browser support still varies; accepting a codec is
not a promise of playback on every browser/OS. MP4 is preferred by capture when
explicit H.264/AAC recording is available. WebM avoids an expensive conversion but
older Safari/iOS versions can have playback gaps. See the
[MDN codec guide](https://developer.mozilla.org/en-US/docs/Web/Media/Guides/Formats/Video_codecs)
and [container guide](https://developer.mozilla.org/en-US/docs/Web/Media/Guides/Formats/Containers).

## Validation, metadata and resource bounds

Forced MP4/WebM demuxing and `file,pipe` protocol allowlisting are unchanged.
Probe declared duration when present; independently check decoded timing and
remuxed duration. Duration-less MediaRecorder WebM is supported. Decode stops at
31 seconds and fails the 30-second rule rather than accepting a clipped recording.
Malformed decode fails with 422; a timeout/resource shortage stays retryable 503.
No validation failure earns points or consumes a capture session.

`-map_metadata -1`, `-map_metadata:s -1` and `-map_chapters -1` remove original
container/stream tags and chapters. H.264 `filter_units=remove_types=6` additionally
removes SEI user data; merely removing container tags would leave this behind.
[FFmpeg documents this bitstream filter](https://www.ffmpeg.org/ffmpeg-bitstream-filters.html#filter_005funits).
Technical display rotation remains so portrait media plays in its intended
orientation. Necessary codec parameters, dimensions and muxer-generated technical
tags remain. Visible faces, text, landmarks and spoken information are content,
not metadata, and are not erased. No claim of camera provenance is made.

Budgets: 20s input probe, 120s decode, 30s remux, 10s output probe. Sanitized size
must remain below configured input byte limit +1 MiB for container overhead.
`MEDIA_CONCURRENCY=1` and `FFMPEG_THREADS=1` bound expensive processing; filters
also use one thread. The production process count remains one. `FFMPEG_PRESET`
has been removed from configuration because no encoder is invoked. Existing
private storage, hash uniqueness, idempotency/lease fencing, caption checks,
capture expiry, atomic scoring and byte/object quota controls remain unchanged.

## Recording guidance

Capture requests 1280×720, 30fps, approximately 2.5Mbps video and 128kbps audio.
Constraints/bitrates are device best-effort; actual preview dimensions are checked
and the server validates the bytes. Recording stops around 29 seconds for timing
headroom. Device settings can still produce unsupported input; the error explains
the problem. Record in the app where supported, or export 720p 8-bit H.264/AAC-LC
MP4 and share through the gallery. Exported gallery uploads earn zero points.
On phones with a “Most Compatible” recording option, choose H.264 instead of
HEVC/HDR and select 720p where available; names/options differ by device. A native
MOV file is not accepted just by renaming its extension. No server conversion is
offered. Camera access requires HTTPS outside localhost.

## Actual evidence and outstanding gates

Fixtures are synthetic, **not Android/iPhone recordings**. Tests cover H.264/AAC
landscape and portrait 720p, VP8/Opus, VP9/Vorbis, streaming WebM without a duration
header, 4.9/5/30/30.1-second boundaries, over-resolution, HEVC/10-bit rejection,
metadata and SEI removal, and unchanged decoded picture hashes. A synthetic MP4
rotation matrix models phone-style orientation. No genuine device fixtures were
found; actual Android/iPhone variable-frame-rate, fragmented Safari MP4, camera
orientation and audio synchronization remain physical-device checks.

Chrome integration uploads/remuxes/plays all three supported codec combinations
from real private MinIO signed URLs and verifies unsigned GET=403. Automated capture
uses synthetic camera/audio. This does not verify Safari, iPhone or Android hardware.

Supporting Windows process-tree tests used native PostgreSQL/MinIO, one processing
job/thread, a configured 512 MiB committed-memory cap and an approximate 0.1 CPU cap.
All 30-second landscape/portrait H.264/AAC fixtures are exactly 52,428,800 bytes
(motion/noise/audio plus a valid MP4 free box). Three runs accepted every video with
3 points, gallery photo with 0 points, feed and rankings:

| Run | Landscape HTTP | Portrait HTTP | High-profile HTTP | Peak committed memory | Aggregate CPU |
|---|---|---|---|---|---|
| Initial remux | 19.77s | 20.27s | Not included | 134,369,280 bytes (~128 MiB) | 5.27s |
| Validation/profile checks | 23.10s | 22.08s | Not included | 137,326,592 bytes (~131 MiB) | 5.95s |
| High-profile coverage | 20.26s | 20.14s | 54.10s | 140,247,040 bytes (~134 MiB) | 10.77s |

The third fixture is confirmed by FFprobe as H.264 High, 30fps, two B-frames,
1280×720, AAC-LC, 30.000 seconds and exactly 50 MiB. The first two fixtures use
Constrained Baseline. Fixture generation uses encoders locally; the upload server
only validates and remuxes. Seven maximum-size HTTP video uploads succeeded.

Artifacts: `.tools/free-tier/windows-720-remux-cpu01.json` and
`windows-720-remux-final-cpu01.json` and `windows-720-high-remux-cpu01.json`.
These are representative workloads, not an
exhaustive CPU/codec adversarial benchmark. Windows Job committed memory differs
from Linux RSS/cgroup accounting. **Docker is unavailable and WSL has no installed
Linux distribution. Linux 512 MiB/0.1 CPU execution and the image build remain
pending; no Render resource compatibility or deployment is claimed.** Repeat the
Linux workload and inspect cgroup peak/OOM events using
[the deployment guide](free-tier-deployment.md#resource-findings-and-deployment-gate)
before provisioning. No services or R2 were activated.

A [manual GitHub Actions container gate](linux-container-verification.md) is now
prepared for a Linux runner without local Docker/WSL. It has not been dispatched;
adding the workflow does not change the pending Linux status.
