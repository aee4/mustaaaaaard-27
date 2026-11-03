import { useEffect, useRef, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { X } from 'lucide-react'
import { api, type Post } from '../api/client'
import { ErrorBox } from './Common'
import { MediaImage } from './MediaImage'

export function PrivateMedia({ group, post, eager = false, priority = false, original = false }: { group: string; post: Post; eager?: boolean; priority?: boolean; original?: boolean }) {
  const container = useRef<HTMLDivElement>(null)
  const [near, setNear] = useState(eager || original)
  const [failed, setFailed] = useState(false)
  const [open, setOpen] = useState(false)
  const attempts = useRef(0)
  const [retryEpoch, setRetryEpoch] = useState(0)
  useEffect(() => {
    const observer = new IntersectionObserver(entries => { if (entries.some(e => e.isIntersecting)) { setNear(true); observer.disconnect() } }, { rootMargin: '200px' })
    if (container.current) observer.observe(container.current)
    return () => observer.disconnect()
  }, [])
  const variant = original || post.kind === 'video' ? 'original' : 'thumbnail'
  const media = useQuery({ queryKey: ['media', group, post.id, variant], queryFn: () => api.media(group, post.id, variant), enabled: near,
    staleTime: query => query.state.data ? Math.max(0, Date.parse(query.state.data.expires_at) - query.state.dataUpdatedAt - 15000) : 0,
    gcTime: 10 * 60_000, retry: false, refetchOnWindowFocus: false })
  function refresh() { setFailed(false); void media.refetch().then(() => setRetryEpoch(value => value + 1)) }
  function error() { if (attempts.current++ < 1) refresh(); else setFailed(true) }
  const width = media.data?.width ?? post.media_width, height = media.data?.height ?? post.media_height
  return <div ref={container} className="private-media" style={{ aspectRatio: width && height ? `${width} / ${height}` : '4 / 3' }}>
    {media.isError ? <ErrorBox error={media.error} retry={() => { attempts.current = 0; refresh() }} />
      : failed ? <div className="media-retry" role="alert"><p>{navigator.onLine ? 'This moment could not load.' : 'You’re offline. Reconnect to load this moment.'}</p><button className="button" onClick={() => { attempts.current = 0; refresh() }}>Retry photo or video</button></div>
        : media.data ? post.kind === 'video' ? <video className="post-media" src={media.data.url} controls playsInline preload={eager ? 'metadata' : 'none'} onError={error} aria-label="Group video" />
          : <><MediaImage key={retryEpoch} src={media.data.url} width={width} height={height} alt="Photo shared with your private group" eager={eager || near} priority={priority} onFailure={error} />{!original && <button className="open-photo" aria-label="Open full-quality photo" onClick={() => setOpen(true)} />}</>
          : <div className="media-placeholder skeleton" role="status"><span className="sr-only">Loading private media</span></div>}
    {open && <PhotoViewer close={() => setOpen(false)}><PrivateMedia group={group} post={post} original eager /></PhotoViewer>}
  </div>
}

function PhotoViewer({ children, close }: { children: React.ReactNode; close: () => void }) {
  const dialog = useRef<HTMLDialogElement>(null)
  useEffect(() => {
    const previous = document.activeElement as HTMLElement
    const overflow = document.body.style.overflow
    const node = dialog.current!
    document.body.style.overflow = 'hidden'; node.showModal()
    return () => { node.close(); document.body.style.overflow = overflow; previous?.focus({ preventScroll: true }) }
  }, [])
  return <dialog ref={dialog} className="photo-viewer" aria-label="Full-quality photo" onCancel={e => { e.preventDefault(); close() }}><button autoFocus className="icon-button" aria-label="Close photo" onClick={close}><X /></button>{children}</dialog>
}
