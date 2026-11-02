import { useEffect, useRef, useState } from 'react'
import { useInfiniteQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { ChevronLeft, ChevronRight, Heart, MessageCircle, Pin, X } from 'lucide-react'
import { api, type Group, type Post, type Session } from '../api/client'
import { Avatar, ErrorBox, Loading } from './Common'
import { ghanaDate, ghanaTime } from '../lib/time'
import { PrivateMedia } from '../pages/Season'

export function Album({ group, post }: { group: string; post: Post }) {
  const [index, setIndex] = useState(0)
  const photos = [post.id, ...(post.album ?? [])]
  return <div className="welcome-album" aria-label="Group welcome album">
    <PrivateMedia key={photos[index]} group={group} post={{ ...post, id: photos[index] }} />
    {photos.length > 1 && <div className="album-controls"><button className="icon-button" aria-label="Previous welcome photo" disabled={index === 0} onClick={() => setIndex(index - 1)}><ChevronLeft /></button><span aria-live="polite">{index + 1} / {photos.length}</span><button className="icon-button" aria-label="Next welcome photo" disabled={index === photos.length - 1} onClick={() => setIndex(index + 1)}><ChevronRight /></button></div>}
  </div>
}

export function SocialActions({ group, post, session }: { group: Group; post: Post; session: Session }) {
  const qc = useQueryClient()
  const [optimistic, setOptimistic] = useState<{ liked: boolean; count: number } | null>(null)
  const [open, setOpen] = useState(false)
  const busy = useRef(false)
  const liked = optimistic?.liked ?? post.liked ?? false
  const count = optimistic?.count ?? post.like_count ?? 0
  const like = useMutation({ mutationFn: (value: boolean) => api.like(group.id, post.id, value),
    onSuccess: async () => { await qc.invalidateQueries({ queryKey: ['feed', group.id] }) },
    onSettled: () => { busy.current = false; setOptimistic(null) } })
  const pin = useMutation({ mutationFn: () => api.pin(group.id, post.id, !post.pinned), onSuccess: () => qc.invalidateQueries({ queryKey: ['feed', group.id] }) })
  return <><div className="social-actions"><button className={`icon-button heart ${liked ? 'liked' : ''}`} aria-label={liked ? 'Unlike post' : 'Like post'} aria-pressed={liked} disabled={like.isPending} onClick={() => {
    if (busy.current) return
    busy.current = true
    setOptimistic({ liked: !liked, count: Math.max(0, count + (liked ? -1 : 1)) }); like.mutate(!liked)
  }}><Heart fill={liked ? 'currentColor' : 'none'} /></button><button className="icon-button" aria-label="Open comments" onClick={() => setOpen(true)}><MessageCircle /></button>
    {post.source === 'system' && group.role === 'admin' && <button className="text-button pin-control" disabled={pin.isPending} onClick={() => pin.mutate()}><Pin size={15} />{post.pinned ? 'Unpin' : 'Pin'}</button>}</div>
    <strong className="like-count" aria-live="polite">{count} {count === 1 ? 'like' : 'likes'}</strong>
    {post.caption && !post.title && <p className="post-caption">{post.caption}</p>}
    <button className="view-comments" onClick={() => setOpen(true)}>View comments ({post.comment_count})</button>
    {like.isError && <ErrorBox error={like.error} />}{pin.isError && <ErrorBox error={pin.error} />}
    {open && <CommentsDialog group={group} post={post} session={session} close={() => setOpen(false)} />}
  </>
}

function CommentsDialog({ group, post, session, close }: { group: Group; post: Post; session: Session; close: () => void }) {
  const dialog = useRef<HTMLDialogElement>(null)
  const qc = useQueryClient()
  const [text, setText] = useState('')
  const retry = useRef<{ text: string; key: string } | null>(null)
  const sending = useRef(false)
  const query = useInfiniteQuery({ queryKey: ['comments', group.id, post.id], initialPageParam: null as string | null,
    queryFn: ({ pageParam }) => api.comments(group.id, post.id, pageParam), getNextPageParam: page => page.next_cursor ?? undefined })
  const refresh = async () => { await Promise.all([qc.invalidateQueries({ queryKey: ['comments', group.id, post.id] }), qc.invalidateQueries({ queryKey: ['feed', group.id] })]) }
  const add = useMutation({ mutationFn: () => api.comment(group.id, post.id, retry.current!.text, retry.current!.key), onSuccess: async () => { retry.current = null; setText(''); await refresh() }, onSettled: () => { sending.current = false } })
  const remove = useMutation({ mutationFn: (id: string) => api.deleteComment(group.id, post.id, id), onSuccess: refresh })
  useEffect(() => { const node = dialog.current!; const previous = document.activeElement as HTMLElement; node.showModal(); return () => { node.close(); previous?.focus() } }, [])
  return <dialog className="comments-dialog" ref={dialog} aria-labelledby="comments-title" onCancel={event => { event.preventDefault(); close() }} onClick={event => { if (event.target === event.currentTarget) close() }}><div className="sheet-handle" /><header><h2 id="comments-title">Comments</h2><button className="icon-button" aria-label="Close comments" onClick={close}><X /></button></header>
    <div className="comments-list">{query.isPending && <Loading />}{query.isError && <ErrorBox error={query.error} retry={() => void query.refetch()} />}
      {query.data?.pages.flatMap(page => page.items).map(comment => <article key={comment.id} className="comment"><Avatar name={comment.author.display_name} /><div><strong>{comment.author.display_name}</strong><p>{comment.text}</p><time dateTime={comment.created_at}>{ghanaTime(comment.created_at)} · {ghanaDate(comment.created_at)}</time>
        {(comment.author.id === session.user.id || group.role === 'admin') && <button className="text-button danger" disabled={remove.isPending} onClick={() => { if (window.confirm('Delete this comment?')) remove.mutate(comment.id) }}>Delete comment</button>}</div></article>)}
      {query.data?.pages[0].items.length === 0 && <p>No comments yet. Say hello.</p>}
      {query.hasNextPage && <button className="button" disabled={query.isFetchingNextPage} onClick={() => void query.fetchNextPage()}>Earlier comments</button>}
    </div>{add.isError && <ErrorBox error={add.error} />}{remove.isError && <ErrorBox error={remove.error} />}
    <form className="comment-composer" onSubmit={event => { event.preventDefault(); if (sending.current || !text.trim() || Array.from(text.trim()).length > 500) return; sending.current = true; retry.current ??= { text: text.trim(), key: crypto.randomUUID() }; add.mutate() }}>
      <label className="sr-only" htmlFor="comment-text">Add a comment</label><textarea id="comment-text" placeholder="Add a comment…" value={text} rows={2} maxLength={1000} disabled={add.isPending || add.isError} onChange={event => setText(event.target.value)} />
      <button className="button yellow" disabled={add.isPending || !text.trim() || Array.from(text.trim()).length > 500}>{add.isPending ? 'Sending…' : add.isError ? 'Retry comment' : 'Send'}</button>
      {add.isError && <button type="button" className="text-button" onClick={() => { retry.current = null; add.reset() }}>Discard retry</button>}
    </form><small>{Array.from(text.trim()).length}/500</small>
  </dialog>
}
