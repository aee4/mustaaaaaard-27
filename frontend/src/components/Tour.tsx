import { useEffect, useRef, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { api } from '../api/client'
import { ErrorBox } from './Common'

const steps = [
  { path: '/', label: 'Feed', title: 'Your everyday moments', text: 'Photos, captions and conversations, shared only with your group.' },
  { path: '/capture', label: 'Capture', title: 'Share your day', text: 'Take a photo or upload from your gallery. Camera photo 1 · camera video 3 · gallery 0 points.' },
  { path: '/leaderboard', label: 'Leaderboard', title: 'A little friendly competition', text: 'See your group’s points and streaks. Likes and comments earn no points.' },
  { path: '/profile', label: 'Profile', title: 'Make yourself at home', text: 'Edit your name, find group invitations and replay this tour whenever you like.' },
]

export function Tour({ user, dirty }: { user: string; dirty: boolean }) {
  const qc = useQueryClient()
  const navigate = useNavigate()
  const status = useQuery({ queryKey: ['tour', user], queryFn: api.tour })
  const [replay, setReplay] = useState(false)
  const [step, setStep] = useState(0)
  const dialog = useRef<HTMLDialogElement>(null)
  const [rect, setRect] = useState<{ x: number; y: number; width: number; height: number } | null>(null)
  const finish = useMutation({ mutationFn: api.completeTour, onSuccess: value => { qc.setQueryData(['tour', user], value); setReplay(false); setStep(0) } })
  const open = !dirty && !!status.data && (!status.data.completed || replay)
  useEffect(() => { const start = () => { setStep(0); setReplay(true) }; window.addEventListener('mustard:replay-tour', start); return () => window.removeEventListener('mustard:replay-tour', start) }, [])
  useEffect(() => {
    if (!open) return
    const previous = document.activeElement as HTMLElement
    const node = dialog.current!
    node.showModal()
    return () => { node.close(); previous?.focus() }
  }, [open])
  useEffect(() => {
    if (!open) return
    function measure() {
      const targets = [...document.querySelectorAll<HTMLElement>(`[data-tour="${steps[step].label}"]`)]
      const target = targets.find(element => element.getClientRects().length > 0)
      const r = target?.getBoundingClientRect()
      setRect(r && r.width > 0 && r.top >= 0 && r.bottom <= window.innerHeight ? { x: r.x, y: r.y, width: r.width, height: r.height } : null)
    }
    const frame = requestAnimationFrame(measure)
    const observer = new ResizeObserver(measure); observer.observe(document.body)
    window.addEventListener('resize', measure); window.addEventListener('scroll', measure, true)
    return () => { cancelAnimationFrame(frame); observer.disconnect(); window.removeEventListener('resize', measure); window.removeEventListener('scroll', measure, true) }
  }, [open, step])
  const boxWidth = Math.min(320, window.innerWidth - 32)
  const left = rect ? Math.max(16, Math.min(rect.x + rect.width / 2 - boxWidth / 2, window.innerWidth - boxWidth - 16)) : Math.max(16, (window.innerWidth - boxWidth) / 2)
  const top = rect ? Math.max(16, Math.min(rect.y > 280 ? rect.y - 255 : rect.y + rect.height + 20, window.innerHeight - 275)) : Math.max(16, (window.innerHeight - 260) / 2)
  function go(value: number) { setStep(value); navigate(steps[value].path) }
  return <dialog ref={dialog} className="tour-dialog" aria-labelledby="tour-title" onCancel={event => { event.preventDefault(); finish.mutate() }}>
    {rect && <><div className="tour-highlight" style={{ left: rect.x - 4, top: rect.y - 4, width: rect.width + 8, height: rect.height + 8 }} />
      <svg className="tour-arrow" aria-hidden="true"><defs><marker id="tour-arrowhead" markerWidth="8" markerHeight="8" refX="5" refY="3" orient="auto"><path d="M0,0 L6,3 L0,6" fill="none" stroke="#ffcb3d" strokeWidth="2" /></marker></defs><path d={`M ${left + boxWidth / 2} ${rect.y > 280 ? top + 230 : top} Q ${left + boxWidth / 2 + 35} ${(top + rect.y) / 2} ${rect.x + rect.width / 2} ${rect.y > 280 ? rect.y - 9 : rect.y + rect.height + 9}`} stroke="#ffcb3d" strokeWidth="4" fill="none" markerEnd="url(#tour-arrowhead)" /></svg></>}
    <section className="tour-tooltip" style={{ left, top, width: boxWidth }}><div className="tour-top"><span>{step + 1} of {steps.length}</span><button className="text-button" disabled={finish.isPending} onClick={() => finish.mutate()}>Skip</button></div><h2 id="tour-title">{steps[step].title}</h2><p>{steps[step].text}</p>{finish.isError && <ErrorBox error={finish.error} />}<div className="button-row"><button className="button" disabled={step === 0 || finish.isPending} onClick={() => go(step - 1)}>Back</button><button autoFocus className="button yellow" disabled={finish.isPending} onClick={() => step === steps.length - 1 ? finish.mutate() : go(step + 1)}>{step === steps.length - 1 ? 'Done' : 'Next'}</button></div></section>
  </dialog>
}
