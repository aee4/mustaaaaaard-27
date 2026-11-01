import { QueryClient, QueryClientProvider, useInfiniteQuery } from '@tanstack/react-query'
import { act, renderHook, waitFor } from '@testing-library/react'
import { expect, it, vi } from 'vitest'
import type { ReactNode } from 'react'
import { api } from './client'
import { feedOptions } from './queries'

it('passes the opaque cursor unchanged and stops on a null next cursor', async () => {
  const feed = vi.spyOn(api, 'feed').mockResolvedValueOnce({ items: [], next_cursor: 'opaque/+==', server_time: '2026-11-01T12:00:00Z' }).mockResolvedValueOnce({ items: [], next_cursor: null, server_time: '2026-11-01T12:00:00Z' })
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  const wrapper = ({ children }: { children: ReactNode }) => <QueryClientProvider client={client}>{children}</QueryClientProvider>
  const { result } = renderHook(() => useInfiniteQuery(feedOptions('private-group')), { wrapper })
  await waitFor(() => expect(result.current.hasNextPage).toBe(true))
  await act(() => result.current.fetchNextPage())
  await waitFor(() => expect(result.current.hasNextPage).toBe(false))
  expect(feed.mock.calls).toEqual([['private-group', null], ['private-group', 'opaque/+==']])
  expect(result.current.data?.pages).toHaveLength(2)
  client.clear()
})
