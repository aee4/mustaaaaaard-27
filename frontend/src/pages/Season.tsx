import { useEffect, useState, type FormEvent } from 'react'
import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { ArrowDown, ArrowUpRight, Camera, ChartNoAxesColumnIncreasing, Check, Copy, Film, Image as ImageIcon, ShieldCheck, Trash2, Trophy, UsersRound } from 'lucide-react'
import { api, type Group, type Invite, type Post, type Rank, type Session } from '../api/client'
import { feedOptions, ownRank } from '../api/queries'
import { Avatar, Countdowns, ErrorBox, Skeleton, Stats } from '../components/Common'
import { ghanaDate, ghanaTime, syncTime } from '../lib/time'
import { scoreLabel } from '../lib/media'
import { SeasonSummary } from '../App'
import { PrivateMedia } from '../components/PrivateMedia'
import { Album, SocialActions } from '../components/Social'

function PostCard({ post, group, session, eager = false, priority = false }: { post: Post; group: Group; session: Session; eager?: boolean; priority?: boolean }) {
  const qc = useQueryClient()
  const remove = useMutation({ mutationFn: () => api.remove(group.id, post.id), onSuccess: () => qc.invalidateQueries() })
  const name = post.source === 'system' ? `${group.name} · Group` : post.author_name || 'Group member'
  return <article className="post-card"><header><Avatar name={name} /><div><h3>{name}</h3><time dateTime={post.accepted_at}>{ghanaTime(post.accepted_at)} · {ghanaDate(post.accepted_at)}</time></div>
    <span className={`score-pill ${post.source === 'gallery' ? 'gallery' : ''}`}>{scoreLabel(post.source, post.points)}</span></header>
    <>{post.title && <div className="welcome-title"><h2>{post.title}</h2><p>{post.caption}</p></div>}{post.source === "system" ? <Album group={group.id} post={post} eager={eager} priority={priority} /> : <PrivateMedia group={group.id} post={post} eager={eager} priority={priority} />}<SocialActions group={group} post={post} session={session} /></><footer><span>{post.kind === 'video' ? <Film size={16} /> : <ImageIcon size={16} />}{post.source === 'gallery' ? 'From the gallery' : 'A little of today'}</span>
      {(post.user_id === session.user.id || group.role === 'admin') && <button className="text-button danger" aria-label={`Remove post by ${name}`} disabled={remove.isPending} onClick={() => {
        if (window.confirm('Remove this moment? Its points and activity will be recalculated. The same file cannot earn points again.')) remove.mutate()
      }}><Trash2 size={15} />Remove</button>}</footer>{remove.isError && <ErrorBox error={remove.error} />}</article>
}

export function FeedPage({ group, session, rank }: { group: Group; session: Session; rank?: Rank }) {
  const feed = useInfiniteQuery(feedOptions(group.id))
  useEffect(() => { if (feed.data?.pages[0]) syncTime(feed.data.pages[0].server_time) }, [feed.data])
  const posts = feed.data?.pages.flatMap(page => page.items) || []
  const welcome = feed.data?.pages[0].pinned
  return <><div className="page-heading feed-page-heading"><h1>Feed</h1><Link className="button yellow desktop-capture" to="/capture"><Camera size={18} />Share a moment</Link></div>
    <div className="feed-layout"><div className="feed-column">
      {welcome && <PostCard post={welcome} group={group} session={session} eager priority />}
      {feed.isPending && <Skeleton kind="feed" />}{feed.isError && <ErrorBox error={feed.error} retry={() => void feed.refetch()} />}
      {!feed.isPending && !feed.isError && posts.length === 0 && !welcome && <section className="empty panel"><div className="empty-icon"><Camera size={32} /></div><span className="eyebrow">THE FIRST PAGE IS YOURS</span><h2>Your group’s first moment</h2><p>No posts yet. Capture something small, or share a memory from your gallery.</p><Link className="button yellow" to="/capture">Make the first memory <ArrowUpRight size={18} /></Link></section>}
      {posts.map((post, index) => <PostCard key={post.id} post={post} group={group} session={session} eager={!welcome && index < 2} priority={!welcome && index === 0} />)}
      {feed.isFetchingNextPage && <Skeleton kind="comments" />}
      {feed.hasNextPage && <button className="button load-more" disabled={feed.isFetchingNextPage} onClick={() => void feed.fetchNextPage()}>{feed.isFetchingNextPage ? 'Loading moments…' : 'A little further back'}<ArrowDown size={16} /></button>}
      {posts.length > 0 && !feed.hasNextPage && <p className="end-note">All caught up. Go make a memory.</p>}
    </div><aside className="feed-aside"><SeasonSummary rank={rank} /><section className="note-card"><span className="eyebrow">A NOTE TO OUR FUTURE SELVES</span><h2>We were here.<br />Together.</h2><p>Not every day has to be a big day. The little ones count too.</p><span className="scribble">The Final Season.</span></section>
      <Link className="text-button" to="/capture">Capture photo +1 · video +3 <ArrowUpRight size={14} /></Link><p className="fine-print">Gallery sharing earns 0 points and does not maintain a streak.</p></aside></div></>
}

export function LeaderboardPage({ group, session }: { group: Group; session: Session }) {
  const [period, setPeriod] = useState<'weekly' | 'all'>('weekly')
  const [offset, setOffset] = useState(0)
  const qc = useQueryClient()
  const query = useQuery({ queryKey: ['ranking', group.id, period, offset], queryFn: () => api.ranks(group.id, period, offset) })
  const own = useQuery({ queryKey: ['own', group.id, session.user.id], queryFn: () => ownRank(group.id, session.user.id) })
  const moderation = useMutation({ mutationFn: (user: string) => api.removeMember(group.id, user), onSuccess: () => qc.invalidateQueries() })
  useEffect(() => { if (query.data) syncTime(query.data.server_time) }, [query.data])
  return <><div className="page-heading leaderboard-heading"><div><h1>Leaderboard</h1></div><Trophy className="heading-icon" size={46} /></div>
    <div className="ranking-layout"><section><div className="tabs" role="group" aria-label="Leaderboard period"><button className={period === 'weekly' ? 'selected' : ''} aria-pressed={period === 'weekly'} onClick={() => { setPeriod('weekly'); setOffset(0) }}>Weekly</button><button className={period === 'all' ? 'selected' : ''} aria-pressed={period === 'all'} onClick={() => { setPeriod('all'); setOffset(0) }}>All time</button></div>
      {query.data && <p className="period-label">{query.data.period_start && query.data.period_end ? `${ghanaDate(query.data.period_start)} — ${ghanaDate(new Date(Date.parse(query.data.period_end) - 1).toISOString())}` : 'THE WHOLE FINAL SEASON'}</p>}
      {query.isPending && <Skeleton kind="leaderboard" />}{query.isError && <ErrorBox error={query.error} retry={() => void query.refetch()} />}
      {moderation.isError && <ErrorBox error={moderation.error} />}
      <ol className="rank-list">{query.data?.items.map(row => <li key={row.user.id} className={row.rank === 1 ? 'first-place' : ''}><span className="place">{row.rank === 1 ? <Trophy size={22} aria-label="First place" /> : row.rank}</span><Avatar name={row.user.display_name} /><div className="rank-person"><strong>{row.user.display_name}{row.user.id === session.user.id && <small> you</small>}</strong><span>{row.streak.current} day streak · {row.capture_photos} photos · {row.capture_videos} videos</span><small>{row.gallery_photos + row.gallery_videos} gallery shares · 0 points</small></div><b className="rank-points">{row.points}<small> pts</small></b>
        {group.role === 'admin' && row.user.id !== session.user.id && <button className="icon-button danger" aria-label={`Remove member ${row.user.display_name}`} disabled={moderation.isPending} onClick={() => {
          if (window.confirm(`Remove ${row.user.display_name} from the group? They will lose access.`)) moderation.mutate(row.user.id)
        }}><Trash2 size={16} /></button>}</li>)}</ol>
      {query.data?.total === 0 && <div className="empty panel"><h2>A table for your people.</h2><p>Active group members will appear here, even before earning points.</p></div>}
      {query.data && query.data.total > 20 && <div className="pagination"><button className="button" disabled={offset === 0} onClick={() => setOffset(offset - 20)}>Previous</button><span>{offset + 1}–{Math.min(offset + 20, query.data.total)} of {query.data.total}</span><button className="button" disabled={offset + 20 >= query.data.total || offset >= 10000} onClick={() => setOffset(offset + 20)}>Next</button></div>}
    </section><aside><section className="panel ranking-season"><h2><ChartNoAxesColumnIncreasing size={27} /> Your season.</h2><div className="profile-totals"><div><b>{own.data?.points ?? '—'}</b><span>points</span></div><div><b>{own.data?.streak.current ?? '—'}</b><span>day streak</span></div><div><b>{own.data ? own.data.capture_photos + own.data.capture_videos + own.data.gallery_photos + own.data.gallery_videos : '—'}</b><span>uploads</span></div></div><div className="grace-note"><ShieldCheck size={27} /><div><h3>{own.data ? own.data.streak.grace_used_this_week ? 'Grace used this week' : 'Grace available' : 'Grace syncing'}</h3><p>One missed day can preserve a live streak. Grace adds no points or active day.</p></div></div>{own.isError && <ErrorBox error={own.error} retry={() => void own.refetch()} />}</section><details className="panel score-explainer"><summary>How it works</summary><span className="eyebrow">HOW IT ADDS UP</span><h2>Every moment counts.</h2><div className="rules-row"><ImageIcon size={20} />Camera photo <b>+1</b></div><div className="rules-row"><Film size={20} />Camera video <b>+3</b></div><div className="rules-row"><ImageIcon size={20} />Gallery sharing <b>0</b></div><p className="fine-print">No daily scoring cap. Equal scores share a rank. Only accepted captures count toward streaks.</p></details><Countdowns /></aside></div></>
}

export function ProfilePage({ group, session, rank, rankError }: { group: Group; session: Session; rank?: Rank; rankError: unknown }) {
  const qc = useQueryClient()
  const [invite, setInvite] = useState<Invite | null>(null)
  const [copied, setCopied] = useState(false)
  const [copyError, setCopyError] = useState(false)
  const rename = useMutation({ mutationFn: (name: string) => api.editName(name), onSuccess: () => qc.invalidateQueries() })
  const createInvite = useMutation({ mutationFn: (uses: number) => api.invite(group.id, uses), onSuccess: value => setInvite(value) })
  const revoke = useMutation({ mutationFn: () => api.revoke(group.id, invite!.id), onSuccess: () => setInvite(null) })
  const link = invite ? `${window.location.origin}/?invite=${encodeURIComponent(invite.token)}` : ''
  async function copy() { try { await navigator.clipboard.writeText(link); setCopied(true); setCopyError(false) } catch { setCopied(false); setCopyError(true) } }
  function edit(event: FormEvent<HTMLFormElement>) { event.preventDefault(); rename.mutate(String(new FormData(event.currentTarget).get('name')).trim()) }
  return <><div className="page-heading"><div><h1>Profile</h1><p>{session.user.display_name}</p><button className="text-button" onClick={() => window.dispatchEvent(new Event("mustard:replay-tour"))}>Replay tour</button></div><Avatar name={session.user.display_name} /></div>
    <div className="profile-layout"><div><section className="panel"><Stats rank={rank} />{rankError != null && <ErrorBox error={rankError} retry={() => void qc.invalidateQueries({ queryKey: ['own'] })} />}
      <div className="grace-note"><ShieldCheck size={30} /><div><h3>{rank ? rank.streak.grace_used_this_week ? 'This week’s grace is used.' : 'One grace day, on us.' : 'Checking your grace…'}</h3><p>A grace day preserves a live streak. It adds no active day or points, and cannot start a new streak.</p></div></div>
      <>{!rank && <Skeleton kind="profile" />}</><div className="profile-totals"><div><b>{rank?.streak.longest ?? '—'}</b><span>longest streak</span></div><div><b>{rank ? rank.capture_photos + rank.capture_videos : '—'}</b><span>scoring captures</span></div><div><b>{rank ? rank.gallery_photos + rank.gallery_videos : '—'}</b><span>gallery shares</span></div></div>
    </section><section className="panel"><h2>What should we call you?</h2><form onSubmit={edit}><label>Display name<input key={session.user.display_name} name="name" defaultValue={session.user.display_name} required minLength={1} maxLength={80} /></label><button className="button yellow" disabled={rename.isPending}>{rename.isSuccess ? <Check size={16} /> : null}{rename.isPending ? 'Saving…' : 'Save name'}</button></form>{rename.isError && <ErrorBox error={rename.error} />}</section></div>
    <aside><section className="note-card"><span className="eyebrow">STREAKS ARE ACTIVE DAYS</span><h2>A little presence.<br />A lasting memory.</h2><p>Multiple scoring captures on one day count as one active day. Gallery sharing never adds a streak day.</p></section><Countdowns />
      {group.role === 'admin' && <section className="panel admin-panel"><span className="eyebrow"><UsersRound size={14} /> GROUP ADMIN</span><h2>Bring your people in.</h2><form onSubmit={e => { e.preventDefault(); createInvite.mutate(Number(new FormData(e.currentTarget).get('uses'))); setCopied(false) }}><label>Invite uses<input type="number" name="uses" min={1} max={1000} defaultValue={1} required /></label><button className="button yellow" disabled={createInvite.isPending || !!invite}>Create 72-hour invite</button></form>
        {createInvite.isError && <ErrorBox error={createInvite.error} />}{invite && <div className="invite-result"><label>Invite link<input readOnly value={link} onFocus={e => e.target.select()} /></label><button className="text-button" onClick={() => void copy()}><Copy size={14} />{copied ? 'Copied' : 'Copy link'}</button>{copyError && <p role="status" className="fine-print">Couldn’t copy automatically. Select the link above and copy it manually.</p>}<button className="text-button danger" disabled={revoke.isPending} onClick={() => revoke.mutate()}>Revoke invite</button><small>Expires {ghanaDate(invite.expires_at)} at {ghanaTime(invite.expires_at)}. Keep the link private.</small></div>}{revoke.isError && <ErrorBox error={revoke.error} />}<p className="fine-print">Remove posts from the feed and members from the leaderboard. Group creators become admins of their own new groups; other admin-role changes use operator bootstrap.</p></section>}
    </aside></div></>
}
