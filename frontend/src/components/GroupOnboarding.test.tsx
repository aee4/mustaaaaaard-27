import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { createMemoryRouter, RouterProvider } from 'react-router-dom'
import { expect, it, vi } from 'vitest'
import App from '../App'
import { api } from '../api/client'

it('shows actionable no-group state and selects the created group on its feed', async () => {
  vi.spyOn(window, 'scrollTo').mockImplementation(() => {})
  vi.spyOn(api, 'session').mockResolvedValue({ user: { id: 'user', display_name: 'Ama' }, csrf_token: 'csrf', expires_at: '2027-01-01' })
  vi.spyOn(api, 'groups').mockResolvedValue([])
  const created = { id: 'new-group', name: 'Our people', role: 'admin' }
  vi.spyOn(api, 'createGroup').mockResolvedValue(created)
  vi.spyOn(api, 'feed').mockResolvedValue({ items: [], next_cursor: null, server_time: '2026-11-01T12:00:00Z' })
  vi.spyOn(api, 'ranks').mockResolvedValue({ items: [{ user: { id: 'user', display_name: 'Ama' }, points: 0, rank: 1, capture_photos: 0, capture_videos: 0, gallery_photos: 0, gallery_videos: 0, streak: { current: 0, longest: 0, grace_used_this_week: false } }], total: 1, offset: 0, limit: 20, period_start: null, period_end: null, server_time: '2026-11-01T12:00:00Z' })
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  const router = createMemoryRouter([{ path: '*', element: <App /> }], { initialEntries: ['/profile'] })
  render(<QueryClientProvider client={client}><RouterProvider router={router} /></QueryClientProvider>)
  expect(await screen.findByRole('heading', { name: 'Your season needs your people.' })).toBeVisible()
  expect(screen.getByRole('button', { name: 'Join with invite' })).toBeVisible()
  fireEvent.click(screen.getByRole('button', { name: 'Create group' }))
  fireEvent.change(screen.getByLabelText('Group name'), { target: { value: 'Our people' } })
  // Once creation commits, refreshed membership returns the same server group.
  vi.mocked(api.groups).mockResolvedValue([created])
  fireEvent.click(screen.getByRole('button', { name: 'Create and open feed' }))
  await waitFor(() => expect(router.state.location.pathname).toBe('/'))
  expect(await screen.findByRole('heading', { name: /Good days start/ })).toBeVisible()
  expect(screen.getByLabelText('Your group')).toHaveValue('new-group')
  expect(api.createGroup).toHaveBeenCalledWith('Our people')
  client.clear()
})
