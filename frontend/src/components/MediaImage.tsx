import { useEffect, useLayoutEffect, useRef, useState } from 'react'

type Props = { src: string; width?: number | null; height?: number | null; alt: string; eager?: boolean; priority?: boolean; onFailure: () => void }

// A new source owns its decode state. Parent updates never remount a valid image.
export function MediaImage(props: Props) { return <DecodedImage key={props.src} {...props} /> }

function DecodedImage({ src, width, height, alt, eager, priority, onFailure }: Props) {
  const node = useRef<HTMLImageElement>(null)
  const [state, setState] = useState<'loading' | 'ready' | 'error'>('loading')
  const failure = useRef(onFailure)
  useEffect(() => { failure.current = onFailure }, [onFailure])
  useLayoutEffect(() => {
    const img = node.current!
    let active = true
    let finished = false
    const fail = () => { if (active && !finished) { finished = true; clearTimeout(timeout); setState('error'); failure.current() } }
    const ready = async () => {
      try { if (img.decode) await img.decode(); if (active && !finished) { finished = true; clearTimeout(timeout); setState('ready') } }
      catch { fail() }
    }
    const timeout = setTimeout(fail, 20000)
    img.addEventListener('load', ready); img.addEventListener('error', fail)
    if (img.complete) { if (img.naturalWidth) void ready(); else fail() }
    return () => { active = false; clearTimeout(timeout); img.removeEventListener('load', ready); img.removeEventListener('error', fail) }
  }, [src])
  return <div className={`media-image ${state}`} style={{ aspectRatio: width && height ? `${width} / ${height}` : '4 / 3' }} aria-busy={state === 'loading'}>
    <img ref={node} src={src} width={width ?? undefined} height={height ?? undefined} alt={alt} loading={eager ? 'eager' : 'lazy'} fetchPriority={priority ? 'high' : 'auto'} decoding="async" />
    {state === 'loading' && <span className="sr-only" role="status">Loading photo</span>}
    {state === 'error' && <span className="sr-only">Photo unavailable</span>}
  </div>
}
