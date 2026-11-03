import { useCallback, useEffect, useRef, useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { useBlocker, useNavigate } from 'react-router-dom'
import { Camera, SwitchCamera, Check, Film, ImagePlus, Info, RotateCcw, Square, UploadCloud, X } from 'lucide-react'
import { api, ApiError, upload, type Capture, type Group, type Kind, type UploadPlan } from '../api/client'
import { Countdowns, ErrorBox } from '../components/Common'
import { GALLERY_LABEL, recordingMime, validateFile } from '../lib/media'
import { captureStill, openCameraStream } from '../lib/photo'
import { serverNow } from '../lib/time'

export function CapturePage({ group, onDirty }: { group: Group; onDirty: (value: boolean) => void }) {
  const qc = useQueryClient()
  const navigate = useNavigate()
  const [source, setSource] = useState<'camera' | 'gallery'>('camera')
  const [kind, setKind] = useState<Kind>('photo')
  const [facing, setFacing] = useState<'user' | 'environment'>('environment')
  const [frameReady, setFrameReady] = useState(false)
  const picker = useRef<HTMLInputElement>(null)
  const [stream, setStream] = useState<MediaStream | null>(null)
  const [capture, setCapture] = useState<Capture | null>(null)
  const [plan, setPlan] = useState<UploadPlan | null>(null)
  const [caption, setCaption] = useState('')
  const [preview, setPreview] = useState('')
  const [error, setError] = useState<unknown>(null)
  const [starting, setStarting] = useState(false)
  const [validating, setValidating] = useState(false)
  const [takingPhoto, setTakingPhoto] = useState(false)
  const [recording, setRecording] = useState(false)
  const [elapsed, setElapsed] = useState(0)
  const [uploading, setUploading] = useState(false)
  const [progress, setProgress] = useState(0)
  const [attempted, setAttempted] = useState(false)
  const [retryAt, setRetryAt] = useState(0)
  const [now, setNow] = useState(() => Date.now())
  const previewUrl = useRef('')
  const video = useRef<HTMLVideoElement>(null)
  const live = useRef<MediaStream | null>(null)
  const recorder = useRef<MediaRecorder | null>(null)
  const generation = useRef(0)
  const tries = useRef(0)
  const accepted = useRef(false)
  const dirty = !!stream || !!plan || starting || uploading || validating || takingPhoto
  const blocker = useBlocker(() => dirty && !accepted.current)
  const stopTracks = useCallback(() => {
    live.current?.getTracks().forEach(track => track.stop())
    live.current = null; setStream(null); setFrameReady(false)
  }, [])
  const clear = useCallback(() => {
    generation.current++
    if (recorder.current && recorder.current.state !== 'inactive') {
      recorder.current.onstop = null; recorder.current.stop()
    }
    recorder.current = null; stopTracks(); setRecording(false); setElapsed(0); setStarting(false); setValidating(false); setTakingPhoto(false)
    if (previewUrl.current) URL.revokeObjectURL(previewUrl.current)
    previewUrl.current = ''; setPreview('')
    setPlan(null); setCaption(''); setCapture(null); setError(null); setAttempted(false); setRetryAt(0); tries.current = 0
  }, [stopTracks])
  useEffect(() => { onDirty(dirty); return () => onDirty(false) }, [dirty, onDirty])
  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), 250)
    const lifetime = generation
    return () => { clearInterval(id); lifetime.current++; if (recorder.current?.state === 'recording') { recorder.current.onstop = null; recorder.current.stop() }; live.current?.getTracks().forEach(t => t.stop()); if (previewUrl.current) URL.revokeObjectURL(previewUrl.current) }
  }, [])
  useEffect(() => {
    const prevent = (event: BeforeUnloadEvent) => { if (dirty) { event.preventDefault(); event.returnValue = '' } }
    window.addEventListener('beforeunload', prevent)
    return () => window.removeEventListener('beforeunload', prevent)
  }, [dirty])
  useEffect(() => {
    if (!stream) return
    if (video.current) video.current.srcObject = stream
    const ended = () => { stopTracks(); setError(new Error('Camera access ended. Check browser settings or device availability, then retry or use the gallery.')) }
    stream.getVideoTracks().forEach(track => track.addEventListener('ended', ended))
    return () => stream.getVideoTracks().forEach(track => track.removeEventListener('ended', ended))
  }, [stream, stopTracks])

  async function openCamera(nextKind = kind, nextFacing = facing) {
    setError(null); stopTracks(); setStarting(true); setKind(nextKind); setFacing(nextFacing)
    const gen = ++generation.current
    try {
      if (!window.isSecureContext || !navigator.mediaDevices?.getUserMedia) throw new Error('Camera access needs HTTPS or localhost and a browser with camera support. You can still share from the gallery.')
      if (nextKind === 'video' && !recordingMime()) throw new Error('This browser cannot record a supported MP4/WebM video. Try a photo or gallery sharing.')
      const permission = await navigator.permissions?.query({ name: 'camera' as PermissionName }).catch(() => null)
      if (permission?.state === 'denied') throw new Error('Camera access is blocked. Enable it in your browser settings, then try again, or share from the gallery.')
      const session = await api.capture(group.id, nextKind)
      if (gen !== generation.current) return
      const media = await openCameraStream(nextKind, nextFacing)
      if (gen !== generation.current) { media.getTracks().forEach(t => t.stop()); return }
      live.current = media; setCapture(session); setStream(media)
      setFacing(media.getVideoTracks()[0]?.getSettings().facingMode === 'user' ? 'user' : nextFacing)
    } catch (e) {
      if (gen === generation.current) setError(e instanceof DOMException && e.name === 'NotAllowedError'
        ? new Error(nextKind === 'video' ? 'Camera or microphone access was denied or dismissed. Check browser settings, try Photo, or use the gallery.' : 'Camera permission denied or dismissed. Check browser settings or use the gallery.')
        : e instanceof DOMException && ['NotReadableError', 'AbortError'].includes(e.name) ? new Error('The camera is busy or unavailable. Close other camera apps and retry, or use the gallery.')
          : e instanceof DOMException && e.name === 'NotFoundError' ? new Error('No camera was found. Connect a camera or use the gallery.') : e)
    } finally { if (gen === generation.current) setStarting(false) }
  }
  async function acceptPreview(file: Blob, session: Capture | null, gen: number) {
    setValidating(true)
    try {
      await validateFile(file, kind)
      if (gen !== generation.current) return
      if (previewUrl.current) URL.revokeObjectURL(previewUrl.current)
      previewUrl.current = URL.createObjectURL(file); setPreview(previewUrl.current)
      setPlan({ group: group.id, kind, file, capture: session, key: crypto.randomUUID() })
      setAttempted(false); tries.current = 0; setError(null)
    } catch (e) { if (gen === generation.current) setError(e) }
    finally { if (gen === generation.current) setValidating(false) }
  }
  async function takePhoto() {
    const track = live.current?.getVideoTracks()[0]
    if (!video.current || !capture || !track || takingPhoto || !frameReady) return
    const gen = generation.current
    setTakingPhoto(true); setError(null)
    try {
      const file = await captureStill(video.current, track)
      if (gen !== generation.current) return
      stopTracks(); await acceptPreview(file, capture, gen)
    } catch (e) { if (gen === generation.current) setError(e) }
    finally { if (gen === generation.current) setTakingPhoto(false) }
  }
  function startRecording() {
    if (!stream || !capture || !frameReady) return
    const mime = recordingMime()
    if (!mime) { setError(new Error('No supported recording format is available.')); return }
    const gen = generation.current
    try {
      const instance = new MediaRecorder(stream, { mimeType: mime, videoBitsPerSecond: 2_500_000, audioBitsPerSecond: 128_000 })
      const chunks: BlobPart[] = []
      const began = performance.now()
      let bytes = 0
      instance.ondataavailable = event => {
        if (event.data.size) { chunks.push(event.data); bytes += event.data.size }
        if (bytes > 50 * 1024 * 1024 && instance.state === 'recording') instance.stop()
      }
      const timer = setInterval(() => {
        const seconds = (performance.now() - began) / 1000
        if (gen === generation.current) setElapsed(seconds)
        // One-second buffer for timer/encoder scheduling; server remains final authority.
        if (seconds >= 29 && instance.state === 'recording') instance.stop()
        if (instance.state === 'inactive') clearInterval(timer)
      }, 100)
      instance.onerror = () => { clearInterval(timer); setError(new Error('Video recording failed. Please retake it.')); stopTracks(); setRecording(false) }
      instance.onstop = () => {
        clearInterval(timer)
        if (gen !== generation.current) return
        setRecording(false); stopTracks()
        if ((performance.now() - began) / 1000 < 5) { setError(new Error('Record for at least 5 seconds. Please retake this video.')); return }
        void acceptPreview(new Blob(chunks, { type: mime }), capture, gen)
      }
      recorder.current = instance; instance.start(250); setRecording(true); setElapsed(0)
    } catch (e) { setError(e); stopTracks() }
  }
  async function choose(file: File | undefined) {
    if (!file) return
    setError(null)
    await acceptPreview(file, null, generation.current)
  }
  async function submit() {
    if (!plan || uploading) return
    if (Array.from(caption).length > 280) { setError(new Error('Caption must be at most 280 characters.')); return }
    const operation = attempted ? plan : { ...plan, caption: caption.trim() || null }
    setPlan(operation)
    const gen = generation.current
    setUploading(true); setProgress(0); setError(null); setAttempted(true); tries.current++
    try {
      const post = await upload(operation, value => { if (gen === generation.current) setProgress(value) })
      void qc.invalidateQueries({ predicate: query => query.queryKey[0] !== 'media' })
      if (gen !== generation.current) return
      if (post.removed) throw new Error('This upload was accepted earlier and then removed. It cannot earn points again. You may discard this preview.')
      accepted.current = true
      clear(); onDirty(false); void qc.invalidateQueries({ predicate: query => query.queryKey[0] !== 'media' }); navigate('/')
    } catch (e) {
      if (gen !== generation.current) return
      setError(e)
      setRetryAt(Date.now() + Math.min(8000, 1000 * 2 ** (tries.current - 1)))
    } finally { if (gen === generation.current) setUploading(false) }
  }
  const remaining = capture ? Math.max(0, Math.floor((Date.parse(capture.expires_at) - (serverNow() ?? now)) / 1000)) : 0
  const expired = !!plan?.capture && remaining === 0
  const retryable = error instanceof ApiError && error.retryable
  return <div className={stream ? 'camera-active' : 'camera-idle'}><div className="page-heading capture-heading"><div><h1>Capture</h1></div></div>
    <div className="capture-layout"><section className="capture-workspace"><div className="tabs capture-sources" role="group" aria-label="Upload source">
      <button className={source === 'camera' ? 'selected' : ''} disabled={uploading || starting} aria-pressed={source === 'camera'} onClick={() => { if (dirty && !window.confirm('Discard this capture?')) return; clear(); setSource('camera') }}><Camera size={19} /> Camera</button>
      <button className={source === 'gallery' ? 'selected' : ''} disabled={uploading || starting || takingPhoto} aria-pressed={source === 'gallery'} aria-label="Upload from gallery" onClick={() => { if (dirty && !window.confirm('Discard this capture?')) return; clear(); setSource('gallery'); picker.current?.click() }}><ImagePlus size={19} /> Upload from gallery</button>
    </div>
    <input ref={picker} className="sr-only" tabIndex={-1} aria-label={`Choose gallery ${kind}`} type="file" accept={kind === 'photo' ? 'image/jpeg,image/png,image/webp' : 'video/mp4,video/webm'} onChange={e => { void choose(e.target.files?.[0]); e.target.value = '' }} />
    {source === 'gallery' && <div className="gallery-label"><ImagePlus size={17} /><strong>{GALLERY_LABEL}</strong><span>No points. No streak activity. Just a memory.</span></div>}
    <div className="kind-switch" role="group" aria-label="Media kind"><button aria-pressed={kind === 'photo'} className={kind === 'photo' ? 'selected' : ''} disabled={!!plan || recording || starting || takingPhoto || validating} onClick={() => { if (stream) void openCamera('photo'); else { clear(); setKind('photo') } }}>Photo</button><button aria-pressed={kind === 'video'} className={kind === 'video' ? 'selected' : ''} disabled={!!plan || recording || starting || takingPhoto || validating} onClick={() => { if (stream) void openCamera('video'); else { clear(); setKind('video') } }}>Video</button></div>
    <div className={`capture-view ${stream || preview ? 'has-media' : ''}`}>
      {stream ? <><video ref={video} className={facing === 'user' ? 'front-camera' : ''} autoPlay playsInline muted aria-label="Live camera preview" onLoadedData={event => setFrameReady(event.currentTarget.videoWidth > 0 && event.currentTarget.readyState >= 2)} onPlaying={event => setFrameReady(event.currentTarget.videoWidth > 0 && event.currentTarget.readyState >= 2)} onResize={event => setFrameReady(event.currentTarget.videoWidth > 0 && event.currentTarget.readyState >= 2)} />{recording && <span className="recording-label"><span /> REC {elapsed.toFixed(1)}s / 29s</span>}</>
        : preview ? kind === 'photo' ? <img src={preview} alt="Your photo preview" /> : <video src={preview} controls playsInline preload="metadata" aria-label="Your video preview" />
        : <div className="camera-placeholder"><span className="viewfinder-corner top-left" /><span className="viewfinder-corner top-right" /><span className="viewfinder-corner bottom-left" /><span className="viewfinder-corner bottom-right" />
          <div className="camera-mark">{source === 'camera' ? <Camera size={48} strokeWidth={1.3} /> : <ImagePlus size={48} strokeWidth={1.3} />}</div><h2>{source === 'camera' ? 'A little of right now.' : 'Some moments deserve a share.'}</h2><p>{source === 'camera' ? 'Your camera opens only when you’re ready.' : 'Choose a photo or a 5–30 second video.'}</p>
          {source === 'camera' ? <button className="button yellow" onClick={() => void openCamera()} disabled={starting}>{starting ? 'Opening camera…' : 'Open camera'}<Camera size={17} /></button> : <button className="button yellow" onClick={() => picker.current?.click()}>Choose {kind}</button>}
        </div>}
    </div>
    {source === 'camera' && <p className="capture-point-note">Photo +1 · Video +3</p>}
    {validating && <p role="status" className="session-status">Checking your preview…</p>}
    {takingPhoto && <p role="status" className="session-status">Taking your photo…</p>}
    {error != null && <ErrorBox error={error} />}
    {capture && <p className={`session-status ${remaining === 0 ? 'danger' : ''}`} role="status">{remaining ? `Capture session · ${Math.floor(remaining / 60)}:${String(remaining % 60).padStart(2, '0')} remaining` : 'Capture session expired. Retake before submitting a new capture.'}</p>}
    {stream && <div className="capture-controls"><button className="icon-button" aria-label="Cancel capture" onClick={clear}><X size={24} /></button>
      {kind === 'photo' ? <button className="shutter" aria-label="Take photo" onClick={() => void takePhoto()} disabled={!remaining || takingPhoto || !frameReady}><Camera size={25} /></button>
        : recording ? <button className="shutter recording" aria-label="Stop recording" disabled={elapsed < 5.1} onClick={() => recorder.current?.stop()}><Square size={22} fill="currentColor" /></button>
          : <button className="shutter" aria-label="Start recording" onClick={startRecording} disabled={!remaining || !frameReady}><Film size={25} /></button>}
      <button className="icon-button" aria-label="Switch camera" disabled={recording || starting || takingPhoto} onClick={() => void openCamera(kind, facing === 'user' ? 'environment' : 'user')}><SwitchCamera size={25} /></button></div>}
    {stream && <p className="session-status">{!frameReady ? 'Waiting for a usable camera frame…' : kind === 'video' ? recording && elapsed < 5.1 ? `${Math.max(0, Math.ceil(5.1 - elapsed))}s minimum` : '5–30 seconds' : '+1 point'}</p>}
    {plan && <div className="preview-actions"><span className="eyebrow">{source === 'gallery' ? GALLERY_LABEL : 'LOOK GOOD? KEEP THIS MOMENT.'}</span>
      <label className="caption-input">Caption (optional)<textarea value={caption} onChange={event => { setCaption(event.target.value); if (!attempted) setError(null) }} maxLength={560} disabled={uploading || attempted} rows={2} placeholder="Final year, same people." aria-invalid={Array.from(caption).length > 280} aria-describedby="caption-help" /></label>
      <p id="caption-help" className={`caption-help ${Array.from(caption).length > 280 ? 'danger' : ''}`}>{Array.from(caption).length}/280 characters{attempted ? ' · Kept with this upload for safe retries.' : ' · A little context, if you like.'}</p>
      {uploading ? <div className="upload-status" role="status"><progress value={progress} max={100} aria-label="Upload progress" /><p>{progress >= 99 ? 'Validating and accepting your moment…' : `Uploading · ${progress}%`}</p></div> : <div className="button-row"><button className="button" onClick={clear}><RotateCcw size={16} />{source === 'camera' ? 'Retake' : 'Choose another'}</button><button className="button yellow" disabled={(!attempted && expired) || (!!error && (!retryable || now < retryAt))} onClick={() => void submit()}><UploadCloud size={18} />{attempted ? now < retryAt ? 'Wait a moment…' : 'Retry same upload' : 'Share this moment'}</button><button className="text-button" onClick={clear}>Cancel</button></div>}
      {attempted && !uploading && <p className="fine-print">Retry sends the exact same file, capture and idempotency key. A lost response may already have been accepted. Retaking discards that retry information.</p>}
    </div>}
    {!stream && <Countdowns />}</section><aside><section className="note-card"><span className="eyebrow">TODAY IS WORTH KEEPING</span><h2>Not perfect.<br />Just <em>present.</em></h2><p>Your table at lunch. The walk back. The people who make it feel like home.</p><span className="scribble">Be here for it.</span></section>
      <details className="panel capture-rules"><summary><Info size={18} /> How it works</summary><p><Check size={15} />Camera photo +1 · video +3</p><p><Check size={15} />Gallery sharing · 0 points, no streak</p><p>Photos: JPEG/PNG/WebP, up to 15 MiB. Videos: 720p maximum (1280 × 720 or portrait), 5–30 seconds, up to 50 MiB. Use 8-bit H.264/AAC-LC MP4 or VP8/VP9 WebM with Opus/Vorbis audio; HEVC/HDR is unsupported.</p><p>Record here for a best-effort 720p, 30 fps recording at about 2.5 Mbps. If your device ignores these settings, export at 720p in a supported format and share from the gallery (0 points). The server checks actual dimensions and codecs and does not resize or convert videos. Recording stops near 29s for a timing buffer.</p><p>Uploads count toward the Ghana day when the server accepts them. Leave enough time before midnight or session expiry.</p><small>Camera sessions cannot prove camera origin or freshness. The server validates every upload. HTTPS is required outside localhost.</small></details>
    </aside></div>
    {blocker.state === 'blocked' && <LeavePrompt stay={() => blocker.reset()} leave={() => { clear(); blocker.proceed() }} />}
  </div>
}

function LeavePrompt({ stay, leave }: { stay: () => void; leave: () => void }) {
  const dialog = useRef<HTMLDialogElement>(null)
  useEffect(() => { const node = dialog.current!; node.showModal(); return () => node.close() }, [])
  return <dialog ref={dialog} className="panel leave-dialog" aria-labelledby="leave-title" onCancel={event => { event.preventDefault(); stay() }} onKeyDown={event => {
    if (event.key !== 'Tab') return
    const buttons = event.currentTarget.querySelectorAll<HTMLButtonElement>('button:not(:disabled)')
    const first = buttons[0], last = buttons[buttons.length - 1]
    if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus() }
    if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus() }
  }}><h2 id="leave-title">Leave this moment?</h2><p>Your recording or preview will be discarded. A sent upload may still be accepted; leaving loses its safe retry information.</p><div className="button-row"><button className="button yellow" onClick={stay}>Stay here</button><button className="button" onClick={leave}>Leave capture</button></div></dialog>
}
