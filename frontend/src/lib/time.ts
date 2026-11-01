let offset: number | null = null
export function syncTime(value: string) { offset = Date.parse(value) - Date.now() }
export function serverNow() { return offset === null ? null : Date.now() + offset }
export const ghanaDate = (value: string | number) => new Intl.DateTimeFormat('en-GB', {
  timeZone: 'Africa/Accra', weekday: 'short', day: 'numeric', month: 'short',
}).format(new Date(value))
export const ghanaTime = (value: string) => new Intl.DateTimeFormat('en-GB', {
  timeZone: 'Africa/Accra', hour: '2-digit', minute: '2-digit',
}).format(new Date(value))
export function countdowns(now: number) {
  const date = new Date(now)
  const nextDay = Date.UTC(date.getUTCFullYear(), date.getUTCMonth(), date.getUTCDate() + 1)
  const daysToMonday = (8 - date.getUTCDay()) % 7 || 7
  const nextWeek = Date.UTC(date.getUTCFullYear(), date.getUTCMonth(), date.getUTCDate() + daysToMonday)
  const format = (ms: number) => {
    const seconds = Math.max(0, Math.floor(ms / 1000))
    const days = Math.floor(seconds / 86400)
    return `${days ? days + 'd ' : ''}${String(Math.floor(seconds % 86400 / 3600)).padStart(2, '0')}:${String(Math.floor(seconds % 3600 / 60)).padStart(2, '0')}:${String(seconds % 60).padStart(2, '0')}`
  }
  return { day: format(nextDay - now), week: format(nextWeek - now) }
}
