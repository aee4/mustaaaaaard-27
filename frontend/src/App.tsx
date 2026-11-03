import { useEffect, useState, type FormEvent } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { NavLink, Route, Routes, useLocation, useNavigate } from 'react-router-dom'
import { Camera, House, ChartNoAxesColumnIncreasing, UserRound, ArrowUpRight, LogOut, ChevronDown, Flame, ShieldCheck } from 'lucide-react'
import { api, setCsrf, type Group, type Session } from './api/client'
import { ownRank } from './api/queries'
import { Avatar, Countdowns, ErrorBox, Loading, Stats } from './components/Common'
import { FeedPage, LeaderboardPage, ProfilePage } from './pages/Season'
import { Tour } from './components/Tour'
import { CapturePage } from './pages/Capture'
import { useReadiness } from './components/Connection'
import { rememberDestination } from './lib/destination'

export function Brand() {
  return <div className="brand"><span>Mustaaaaaard <i>’27</i></span><small><svg viewBox="0 0 48 16" aria-hidden="true"><path d="M3 12Q19-4 24 7T45 5" fill="none" stroke="currentColor" strokeWidth="6" strokeLinecap="round" /></svg>The Final Season.</small></div>
}

function Login({ onLogin, sessionPending = false }: { onLogin: (session: Session) => void; sessionPending?: boolean }) {
  const connection = useReadiness()
  const available = !sessionPending && (connection === 'ready' || connection === 'idle')
  const [error, setError] = useState<unknown>(null)
  const [pending, setPending] = useState(false)
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setError(null); setPending(true)
    const form = new FormData(event.currentTarget)
    try { onLogin(await api.devLogin(String(form.get('subject')), String(form.get('name')))) }
    catch (e) { setError(e) } finally { setPending(false) }
  }
  return <div className="login-layout"><div className="login-story"><Brand /><div className="chapter">ONE LAST YEAR. ALL OUR LITTLE MOMENTS.</div>
    <h1>The Final Season 💛</h1><p>Our people. Our everyday moments.</p>
    <div className="season-stamp" aria-hidden="true"><span>MAKE IT COUNT</span><b>’27</b><small>MEMORIES IN THE MAKING</small></div>
    <footer>PRIVATE GROUP · EVERYDAY MOMENTS · OUR FINAL YEAR</footer></div>
    <main className="login-form"><span className="eyebrow">WELCOME BACK, FRIEND</span><h2>Welcome to Mustaaaaaard ’27</h2>
      <p>Capture a little of today. Keep a little of this year.</p>
      <a role="link" className="button dark w-full" aria-disabled={!available} tabIndex={available ? 0 : -1} href={available ? `/auth/google?return_to=${encodeURIComponent(window.location.pathname + window.location.search)}` : undefined} onClick={e => { if (!available) e.preventDefault(); else rememberDestination() }}>Continue with Google <ArrowUpRight size={18} /></a>
      {import.meta.env.DEV && import.meta.env.VITE_DEV_LOGIN === 'true' && <form onSubmit={submit} className="dev-login">
        <span className="eyebrow">LOCAL DEVELOPMENT LOGIN</span>
        <label>Development ID<input name="subject" required pattern="[a-zA-Z0-9_-]{1,80}" placeholder="alice" autoComplete="username" /></label>
        <small className="dev-id-hint">IDs are case-sensitive. The bootstrapped local admin ID is alice.</small>
        <label>Display name<input name="name" required maxLength={80} placeholder="Your name" autoComplete="nickname" /></label>
        <button className="button yellow w-full" disabled={pending || !available}>{pending ? 'Signing in…' : 'Enter the season'}<ArrowUpRight size={18} /></button>
        <small>Development only. Create your own group or join with an invite. The initial group uses explicit admin bootstrap.</small>
      </form>}
      {error != null && <ErrorBox error={error} />}<p className="privacy-note"><ShieldCheck size={18} /> Just your group. Never a public feed.</p>
    </main></div>
}

function JoinForm({ initialToken = '', onJoined }: { initialToken?: string; onJoined: (g: Group) => Promise<void> }) {
  const [token, setToken] = useState(initialToken)
  const [pending, setPending] = useState(false)
  const [error, setError] = useState<unknown>(null)
  async function submit(event: FormEvent) {
    event.preventDefault(); setPending(true); setError(null)
    try {
      let value = token.trim()
      if (value.startsWith('http')) value = new URL(value).searchParams.get('invite') || ''
      const group = await api.join(value); setToken(''); await onJoined(group)
    } catch (e) { setError(e) } finally { setPending(false) }
  }
  return <form className="join-form" onSubmit={submit}><label>Invite token or link<input value={token} onChange={e => setToken(e.target.value)} required autoComplete="off" placeholder="Paste your invite here" /></label>
    <button className="button yellow" disabled={pending}>{pending ? 'Joining…' : 'Join your people'}<ArrowUpRight size={16} /></button>
    {error != null && <ErrorBox error={error} />}</form>
}

function GroupOnboarding({ empty, initialToken, onComplete }: { empty: boolean; initialToken: string; onComplete: (g: Group) => Promise<void> }) {
  const [action, setAction] = useState<'choose' | 'create' | 'join'>(initialToken ? 'join' : 'choose')
  const [pending, setPending] = useState(false)
  const [error, setError] = useState<unknown>(null)
  async function create(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setPending(true); setError(null)
    const name = String(new FormData(event.currentTarget).get('groupName')).trim()
    try {
      if (!name || Array.from(name).length > 100) throw new Error('Enter a group name with 1–100 characters.')
      await onComplete(await api.createGroup(name))
    }
    catch (e) { setError(e) } finally { setPending(false) }
  }
  return <section className="panel join-panel onboarding-panel" aria-labelledby="group-onboarding-title">
    <span className="eyebrow">{empty ? 'YOUR FIRST CHAPTER STARTS HERE' : 'MORE OF YOUR PEOPLE'}</span>
    <h2 id="group-onboarding-title">{empty ? 'Your season needs your people.' : 'A place for every group.'}</h2>
    <p>{empty ? 'You haven’t joined a group yet. Create a private group for your friends, or join one with an invite.' : 'Start another private group, or join your friends using their invite link.'}</p>
    <div className="onboarding-actions" role="group" aria-label="Group actions">
      <button className={`button ${action === 'create' ? 'yellow' : ''}`} aria-pressed={action === 'create'} disabled={pending} onClick={() => { setAction('create'); setError(null) }}>Create group</button>
      <button className={`button ${action === 'join' ? 'yellow' : ''}`} aria-pressed={action === 'join'} disabled={pending} onClick={() => { setAction('join'); setError(null) }}>Join with invite</button>
    </div>
    {action === 'create' && <form className="create-group-form" onSubmit={create}><label>Group name<input name="groupName" required minLength={1} maxLength={200} placeholder="Our final-year people" autoComplete="off" /></label>
      <p className="fine-print">1–100 characters. You’ll be this group’s admin. It stays private; friends join by invite.</p>
      <button className="button yellow" disabled={pending}>{pending ? 'Creating group…' : 'Create and open feed'}<ArrowUpRight size={16} /></button>
      {error != null && <ErrorBox error={error} />}
    </form>}
    {action === 'join' && <JoinForm initialToken={initialToken} onJoined={onComplete} />}
  </section>
}

export default function App() {
  const connection = useReadiness()
  const available = connection === 'ready' || connection === 'idle'
  const qc = useQueryClient()
  const navigate = useNavigate()
  const location = useLocation()
  useEffect(() => { window.scrollTo(0, 0) }, [location.pathname])
  const [selected, setSelected] = useState('')
  const [dirty, setDirty] = useState(false)
  const [joining, setJoining] = useState(() => !!new URLSearchParams(window.location.search).get('invite'))
  const [initialInvite] = useState(() => new URLSearchParams(window.location.search).get('invite') || '')
  const [logoutError, setLogoutError] = useState<unknown>(null)
  const session = useQuery({ queryKey: ['session'], queryFn: api.session, enabled: available, retry: false, staleTime: 60_000 })
  const groups = useQuery({ queryKey: ['groups', session.data?.user.id], queryFn: api.groups, enabled: !!session.data })
  const group = groups.data?.find(g => g.id === selected) || groups.data?.find(g => g.name === 'Mustaaaaaard ’27') || groups.data?.[0]
  const own = useQuery({ queryKey: ['own', group?.id, session.data?.user.id],
    queryFn: () => ownRank(group!.id, session.data!.user.id), enabled: !!group && !!session.data })
  useEffect(() => {
    const expired = () => { qc.removeQueries({ predicate: q => q.queryKey[0] !== 'session' }); qc.setQueryData(['session'], null); setCsrf(null) }
    window.addEventListener('mustard:session-expired', expired)
    return () => window.removeEventListener('mustard:session-expired', expired)
  }, [qc, initialInvite])
  async function joined(value: Group) {
    const key = ['groups', session.data!.user.id]
    await qc.cancelQueries({ queryKey: key })
    qc.setQueryData<Group[]>(key, previous => [...(previous || []).filter(g => g.id !== value.id), value])
    setSelected(value.id); setJoining(false); navigate('/')
    void qc.invalidateQueries({ queryKey: key })
  }
  async function logout() {
    if (dirty && !window.confirm('Leave and discard your capture? An upload already sent may still be accepted.')) return
    try { await api.logout(); setCsrf(null); qc.clear(); qc.setQueryData(['session'], null); setSelected(''); navigate('/') }
    catch (e) { setLogoutError(e) }
  }
  if (session.isPending) return <Login sessionPending onLogin={value => qc.setQueryData(['session'], value)} />
  if (session.isError && !session.data) return <div className="welcome-loading"><Brand /><ErrorBox error={session.error} retry={() => void session.refetch()} /></div>
  if (!session.data) return <Login sessionPending={session.isFetching} onLogin={value => { qc.setQueryData(['session'], value); navigate('/') }} />
  return <div className="app-layout"><aside className="sidebar"><Brand /><Nav /></aside>
    <div className="app-content"><header className={`topbar ${location.pathname === '/' ? 'feed-topbar' : 'inner-topbar'}`}><div className="mobile-brand"><Brand /></div><div className="group-picker">
      <label className="sr-only" htmlFor="group">Your group</label><select id="group" value={group?.id || ''} onChange={e => {
        if (dirty && !window.confirm('Discard your capture and change groups? A sent upload may still be accepted.')) return
        setSelected(e.target.value)
        if (!dirty) navigate('/')
      }}><option value="" disabled>Select group</option>{groups.data?.map(g => <option key={g.id} value={g.id}>{g.name}</option>)}</select><ChevronDown size={14} /></div>
      <span className="streak-badge"><Flame size={19} />{own.data?.streak.current ?? "—"} day streak</span><div className="account"><button className="text-button join-link" aria-label="Manage groups" disabled={dirty} title={dirty ? 'Finish or cancel this capture before managing groups' : 'Create or join a group'} onClick={() => setJoining(!joining)}>Groups</button><Avatar name={session.data.user.display_name} /><button aria-label="Log out" className="icon-button" onClick={() => void logout()}><LogOut size={18} /></button></div>
    </header>
    <main className="main" id="main"><a className="skip-link" href="#page-content">Skip to content</a>
      {logoutError != null && <ErrorBox error={logoutError} />}
      {groups.isError && <ErrorBox error={groups.error} retry={() => void groups.refetch()} />}
      {groups.isPending && <Loading text="Opening your group…" />}
      {!dirty && groups.isSuccess && (joining || !group) && <GroupOnboarding key={session.data.user.id} empty={!group} initialToken={initialInvite} onComplete={joined} />}
      {group && <div id="page-content"><Routes>
        <Route path="/" element={<FeedPage key={group.id} group={group} session={session.data} rank={own.data} />} />
        <Route path="/capture" element={<CapturePage key={group.id} group={group} onDirty={setDirty} />} />
        <Route path="/leaderboard" element={<LeaderboardPage key={group.id} group={group} session={session.data} />} />
        <Route path="/profile" element={<ProfilePage key={group.id} group={group} session={session.data} rank={own.data} rankError={own.error} />} />
        <Route path="*" element={<section className="empty"><h1>A little off course.</h1><NavLink to="/">Back to the feed</NavLink></section>} />
      </Routes></div>}
    </main><footer className="page-footer">Our everyday. Our people. Our final season.<span>Mustaaaaaard ’27</span></footer></div>
    <div className="mobile-nav"><Nav /></div>{group && <Tour key={session.data.user.id} user={session.data.user.id} dirty={dirty} />}
  </div>
}

function Nav() {
  return <nav aria-label="Main navigation">{[
    { to: '/', label: 'Feed', Icon: House }, { to: '/capture', label: 'Capture', Icon: Camera },
    { to: '/leaderboard', label: 'Leaderboard', Icon: ChartNoAxesColumnIncreasing }, { to: '/profile', label: 'Profile', Icon: UserRound },
  ].map(({ to, label, Icon }) => <NavLink data-tour={label} key={to} to={to} end={to === '/'} className={({ isActive }) => `nav-item ${isActive ? 'active' : ''} ${label === 'Capture' ? 'capture-nav' : ''}`}><span><Icon size={23} /></span>{label}</NavLink>)}</nav>
}

export function SeasonSummary({ rank }: { rank: Parameters<typeof Stats>[0]['rank'] }) {
  return <section className="panel season-summary"><span className="eyebrow">A LITTLE EVERY DAY</span><h2>Your season, so far.</h2><Stats rank={rank} /><Countdowns /></section>
}
