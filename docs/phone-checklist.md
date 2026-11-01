# Physical-phone verification (not performed)

For exact Windows/Android/iPhone instructions without custom DNS, use
[phone-https.md](phone-https.md): private IP + restricted HTTPS 3443/9443, certificate
installation/trust, backend Origin/cookie/media configuration and teardown. The
hostname-based example below remains an alternative. Neither is claimed tested
on a physical phone. Optional captions are now part of the acceptance checklist.

Automated tests use desktop Chrome with a phone-sized viewport and synthetic
video/audio devices. They do not establish iPhone, Android, Safari, mobile Firefox,
real microphone, real-camera rotation, backgrounding or cellular compatibility.
Google account consent login is still unverified. No public deployment is needed
for the following private-LAN procedure.

## Private HTTPS without public development authentication

1. Use a trusted private Wi-Fi network and a disposable DB/bucket. Keep FastAPI,
   Vite and MinIO on 127.0.0.1. Do not create public tunnels, enable router port
   forwarding or bind development authentication directly to a public interface.
2. Install a local TLS reverse proxy such as Caddy on the workstation. Configure
   private LAN DNS for `mustard.test` and `media.mustard.test` pointing only to the
   workstation's LAN address. Allow the TLS port in the host firewall only for the
   test phone/private subnet. Use your actual private IP in the example below.
3. Example Caddyfile (illustrative; Caddy/physical-phone TLS was not run here):

   ```caddyfile
   mustard.test {
     bind 192.168.1.10
     tls internal
     reverse_proxy 127.0.0.1:3000
   }
   media.mustard.test {
     bind 192.168.1.10
     tls internal
     reverse_proxy 127.0.0.1:59000
   }
   ```

   Trust that proxy's local CA certificate on the test phone using its OS certificate
   settings (including full trust where required). Don't click through an untrusted
   certificate and assume camera APIs will work. Access logs should stay disabled;
   signed URL query strings and OAuth callbacks must not be logged.
4. Set frontend `FRONTEND_HOST=mustard.test`, `API_TARGET=http://127.0.0.1:58000`,
   `VITE_DEV_LOGIN=true`. Restart Vite. Keep its bind address at loopback; only the
   restricted private proxy is LAN-accessible.
5. Set backend `ENVIRONMENT=development`, `DEV_AUTH=true`, `COOKIE_SECURE=true`,
   `BASE_URL=https://mustard.test`, `ALLOWED_ORIGINS=["https://mustard.test"]`,
   `S3_ENDPOINT=http://127.0.0.1:59000` and
   `S3_PUBLIC_ENDPOINT=https://media.mustard.test`, then restart it. Use the matching
   MinIO bucket/credentials. Media signing must use the actual HTTPS host; never
   rewrite a signed URL afterward. No storage path-prefix stripping is used.
6. Open https://mustard.test on the phone. Check that the browser reports a secure
   context and loads media from the separate HTTPS media host without mixed-content
   errors. If JavaScript needs cross-origin canvas/media reads, configure exact
   bucket CORS without granting anonymous read access. The current feed uses native
   img/video elements.
7. When finished revoke test sessions/membership, stop the proxy and restore firewall
   restrictions. Do not publish this development-auth setup. Production must reject
   dev auth and use its existing Google/secure-cookie requirements.

## Short device checklist

- [ ] Record exact OS/browser versions on at least iPhone Safari and Android Chrome.
- [ ] Login, join via invite, switch group, refresh page and log out; no auth tokens in localStorage.
- [ ] Grant/deny camera and microphone; recover from denial without reloading the app.
- [ ] Photo: front/back device selection as supported by the browser, portrait/landscape,
  preview, retake, cancel and accepted upload. Confirm tracks stop on cancel/leave.
- [ ] Video: supported MIME negotiation, 5s minimum, automatic stop near 29s, sound,
  orientation, preview and playback after server sanitation. Try backgrounding/locking
  the phone during recording; discard/retry safely if the browser pauses timers.
- [ ] Check best-effort 720p/30fps capture and actual accepted dimensions in both
  orientations. Play H.264/AAC-LC MP4 and VP8/VP9 WebM across both phones; older
  Safari may not support WebM. Confirm >720p, HEVC/HDR and native MOV are rejected
  clearly, with no conversion. Exported gallery videos earn 0 points. See
  [video-processing.md](video-processing.md); no genuine phone fixtures were tested.
- [ ] Gallery photo/video validation, oversized/unsupported files, gallery=0 and no
  streak credit. Browser metadata may be incomplete; the server remains authoritative.
- [ ] Optional caption: blank, multiline/emoji,280-character boundary, plain text
  rather than HTML, same caption on retries, and cleared text after post removal.
- [ ] Slow/disconnected upload, lost response, same-key retry, expired capture, signed
  media expiry/refresh, membership revocation while a feed is open.
- [ ] Cursor feed, weekly/all-time ranking, own/admin deletion, grace status and Ghana
  day/week countdowns; no horizontal overflow, comfortable controls, safe-area insets.
- [ ] Keyboard/screen-reader labels, focus visibility, dialog focus and reduced motion.
- [ ] Actual Google login after registering the private callback and providing real
  credentials; synthetic OIDC tests are not a replacement for that check.

No items above are marked passed for a physical phone. Browser capture sessions
discourage casual misuse but cannot prove camera provenance or content freshness.
