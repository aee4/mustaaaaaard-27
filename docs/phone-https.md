# Android and iPhone acceptance over private HTTPS

**Status:** instructions, not physical-device verification. Desktop Chrome tests
used synthetic devices. No Android/iPhone, Caddy installation, firewall change or
private-LAN TLS setup was executed by the agent. The app currently runs on loopback
HTTP; that URL is not a phone camera URL.

This recipe uses the PC's private IPv4 address and two HTTPS ports, so no custom
phone DNS, public hostname, public tunnel, hosting or port forwarding is needed.
Caddy supports internal certificates for IP addresses; clients must trust its CA.
[Caddy HTTPS documentation](https://caddyserver.com/docs/automatic-https).

## 1. PC and network

Use trusted private Wi-Fi. Connect the PC and phones to that same network, with
client isolation disabled. In PowerShell at the repository root, run `ipconfig`;
find the active Wi-Fi/Ethernet IPv4 address. Find each phone's current Wi-Fi address
in its network details. Reserve those DHCP addresses for the test if practical.

The examples use **192.168.1.10 for the PC**, **192.168.1.21 for Android** and
**192.168.1.22 for iPhone**. Replace them with your actual private addresses in
every command/config below. Do not use your router's public/WAN address.

Download the Windows executable from [Caddy](https://caddyserver.com/download),
place it at `.tools/caddy.exe`. No paid service is required. Keep Vite, FastAPI,
PostgreSQL and MinIO bound to 127.0.0.1 using the README's native startup commands.

## 2. Restrict access before starting the proxy

In an **Administrator PowerShell** terminal, create a firewall rule limited to the
two test phones, the PC's LAN address, TCP 3443/9443, Caddy and the Private profile:

```powershell
$lanIp='192.168.1.10'
$phoneIps=@('192.168.1.21','192.168.1.22')
$caddyPath=(Resolve-Path '.tools/caddy.exe').Path
New-NetFirewallRule -DisplayName 'Mustard phone acceptance TLS' -Direction Inbound -Action Allow -Profile Private -Protocol TCP -LocalAddress $lanIp -LocalPort 3443,9443 -RemoteAddress $phoneIps -Program $caddyPath
```

Keep the firewall's default inbound blocking enabled. Do not accept a broad
Windows “allow on all networks” prompt, and remove/restrict any preexisting broad
Caddy allow rule. Do not open ports 3000/58000/59000, create public tunnels or enable
router forwarding/UPnP rules for this test. Caddy will bind only the chosen private
IPv4 address. Use an administrator terminal only for firewall management.

## 3. Start the private TLS proxy

Save this as `.tools/Caddyfile` (replace both occurrences of the PC address):

```caddyfile
{
    auto_https disable_redirects
    skip_install_trust
    storage file_system .tools/caddy-data
}
https://192.168.1.10:3443 {
    bind 192.168.1.10
    tls internal
    reverse_proxy 127.0.0.1:3000
}
https://192.168.1.10:9443 {
    bind 192.168.1.10
    tls internal
    reverse_proxy 127.0.0.1:59000
}
```

From the repository root in a regular PowerShell terminal:

```powershell
& .tools/caddy.exe validate --config .tools/Caddyfile --adapter caddyfile
& .tools/caddy.exe run --config .tools/Caddyfile --adapter caddyfile
```

The configuration uses a private CA, disables HTTP redirects, avoids automatic
system trust installation, and stores CA state under ignored `.tools/caddy-data`.
No access-log directive is enabled. Never enable credential/query/body logging.
See [Caddy global options](https://caddyserver.com/docs/caddyfile/options).

After first startup, the **public** CA certificate is
`.tools/caddy-data/pki/authorities/local/root.crt`. Transfer only that file to each
phone. Never transfer root.key, intermediate keys, `.env` or authentication cookies.

## 4. Restart the backend for the phone origin

Stop the existing backend process (Ctrl+C in its owning terminal). If it was started
by the agent, inspect `Get-NetTCPConnection -LocalAddress 127.0.0.1 -LocalPort 58000
-State Listen` and stop only that identified local acceptance process before restart.
Do not stop an unrelated process. Keep PostgreSQL/MinIO running. In the backend shell:

```powershell
$env:DATABASE_URL='postgresql+psycopg://mustard@127.0.0.1:55432/mustard_handoff_test'
$env:S3_ENDPOINT='http://127.0.0.1:59000'
$env:S3_PUBLIC_ENDPOINT='https://192.168.1.10:9443'
$env:ENVIRONMENT='development'
$env:DEV_AUTH='true'
$env:COOKIE_SECURE='true'
$env:BASE_URL='https://192.168.1.10:3443'
$env:ALLOWED_ORIGINS='["https://192.168.1.10:3443"]'
$env:FFMPEG=(Resolve-Path '.tools/ffmpeg/ffmpeg-9.0.2-essentials_build/bin/ffmpeg.exe').Path
$env:FFPROBE=(Resolve-Path '.tools/ffmpeg/ffmpeg-9.0.2-essentials_build/bin/ffprobe.exe').Path
uv run --directory backend alembic upgrade head
uv run --directory backend uvicorn app.main:app --host 127.0.0.1 --port 58000 --no-access-log
```

Vite must run in a separate shell with:

```powershell
$env:API_TARGET='http://127.0.0.1:58000'
$env:VITE_DEV_LOGIN='true'
npm.cmd run dev --prefix frontend
```

Vite permits IP hosts by default. Backend Origin must match the full HTTPS origin
including 3443. Media uses 9443 at the root; never rewrite a signed URL's host/path.
Two ports on this trusted PC are used only for local testing. For permanent hosting,
follow the production Google/private-storage requirements, not this dev-auth recipe.

## 5. Android Chrome (Pixel / stock Android 14+ menu example)

1. Transfer root.crt to the phone's Downloads folder via USB or a trusted channel.
2. Open Settings → Security & privacy → More security settings → Encryption &
   credentials → Install a certificate → **CA certificate**. Confirm the test-CA
   warning, unlock the phone and select root.crt. Choose CA, not a VPN/user-key or
   Wi-Fi identity certificate. Samsung/OEM labels differ; search Settings for
   “Install a certificate” if needed. Managed phones may disallow this; don't bypass
   their policy. Google's settings guidance is [here](https://support.google.com/pixelphone/answer/2844832?hl=en).
3. Close/reopen Chrome. Open **https://192.168.1.10:3443**. There must be no
   certificate warning; don't bypass a warning or disable certificate validation.
4. Log in as alice, or use a second development ID and join with an admin invite.
   Open Capture → Open camera and allow the actual camera/microphone prompts.
5. Run the checklist below and record device/Android/Chrome versions and outcomes.

## 6. iPhone Safari

1. Transfer only root.crt, for example as an attachment to yourself. Open it on the
   iPhone and allow the certificate profile download. It must be the CA generated
   on your own PC, not an unknown third-party profile.
2. Settings → **Profile Downloaded** → Install; enter your passcode and confirm.
   If needed use General → VPN & Device Management to locate the downloaded
   certificate profile. [Apple installation guidance](https://support.apple.com/en-ie/102400).
3. Settings → General → About → **Certificate Trust Settings** → enable full trust
   for the installed Caddy root. Installing the profile alone does not enable TLS
   trust. [Apple trust guidance](https://support.apple.com/en-us/102390).
4. Close/reopen Safari, open **https://192.168.1.10:3443**, and ensure there is no
   certificate warning. Use Safari itself, not an embedded mail/social-app browser.
5. Log in, open Capture and allow camera/microphone. Record iPhone/iOS/Safari
   versions and run the same checklist. Real Safari codec support is not assumed.

## 7. Acceptance and teardown

- Check /api/ready on the HTTPS app origin: it must show `{"ok":true}`.
- Two users: invite join; photo 1, video 3; gallery 0/no streak; caption/plain-text
  line breaks, 280-character validation; feed, video playback and both rankings.
- Preview/retake/cancel, camera light/track shutdown, permission denial, portrait/
  landscape, 5-second minimum, automatic stop near 29 seconds, background/lock and
  slow/disconnected upload. Retry unchanged bytes/caption/key after uncertain result.
- Old signed URLs may work until short expiry. Verify refreshed media uses the
  HTTPS 9443 endpoint without mixed-content or certificate errors.
- Use [phone-checklist.md](phone-checklist.md) to record actual results. None of
  these physical checks is marked passed by desktop synthetic tests.
- Log out on both phones, stop Caddy, remove **only** the test CA/profile from each
  phone, and remove the rule using administrator PowerShell:
  `Remove-NetFirewallRule -DisplayName 'Mustard phone acceptance TLS'`.
- To return to PC HTTP, restart API with COOKIE_SECURE=false,
  BASE_URL=http://localhost:3000, ALLOWED_ORIGINS including http://localhost:3000,
  and clear S3_PUBLIC_ENDPOINT. Keep all native service binds on loopback.

No phone certificate, firewall rule or public access was configured automatically.
## Video acceptance update — 2026-11-01

Before phone testing, read [video processing](video-processing.md). Capture requests
720p/30fps and 2.5Mbps; devices can ignore those requests. Actual new uploads must
be <=720p (long edge <=1280, short edge <=720), 5–30s, <=50 MiB. Use 8-bit
H.264/AAC-LC MP4 or VP8/VP9 Opus/Vorbis WebM. HEVC/HDR and native MOV are not
converted. Export compatible 720p MP4 for gallery sharing (0 points).

On both Android Chrome and iPhone Safari, test landscape and portrait capture,
5s/near-29s recording, audio sync, retake, upload, feed playback and gallery labels.
Also verify a >720p or HEVC gallery file is clearly rejected. Check cross-device
playback: older Safari can lack WebM support. Synthetic Chrome tests passed;
**physical Android/iPhone and Safari tests remain unperformed**. Use the existing
private HTTPS instructions above; do not expose development authentication publicly.
