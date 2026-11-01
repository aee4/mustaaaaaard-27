import { infiniteQueryOptions } from '@tanstack/react-query'
import { api, ApiError, type Rank } from './client'

export const feedOptions = (group: string) => infiniteQueryOptions({
  queryKey: ['feed', group], initialPageParam: null as string | null,
  queryFn: ({ pageParam }) => api.feed(group, pageParam),
  getNextPageParam: page => page.next_cursor ?? undefined,
})

export async function ownRank(group: string, user: string): Promise<Rank> {
  for (let offset = 0; offset <= 10000; offset += 20) {
    const page = await api.ranks(group, 'all', offset)
    const row = page.items.find(item => item.user.id === user)
    if (row) return row
    if (offset + page.items.length >= page.total) break
  }
  throw new ApiError(404, 'ranking_unavailable', 'Your ranking is not currently available. Refresh your group membership.')
}
