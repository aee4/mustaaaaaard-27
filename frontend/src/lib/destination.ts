const key = 'mustard:login-destination'
export function rememberDestination() {
  try { sessionStorage.setItem(key, window.location.pathname + window.location.search) } catch { /* URL return_to remains available. */ }
}
export function restoreDestination() {
  if (new URLSearchParams(window.location.search).get('connection_retry') !== '1') return
  let destination = '/'
  try { destination = sessionStorage.getItem(key) || '/' } catch { /* Storage may be disabled. */ }
  try {
    const target = new URL(destination, window.location.origin)
    if (!destination.startsWith('/') || destination.startsWith('//') || target.origin !== window.location.origin || target.pathname.startsWith('/auth')) destination = '/'
  } catch { destination = '/' }
  window.history.replaceState(null, '', destination)
}
