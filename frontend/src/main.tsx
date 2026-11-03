import React from 'react'
import ReactDOM from 'react-dom/client'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { createBrowserRouter, RouterProvider } from 'react-router-dom'
import App from './App'
import { ApiError } from './api/client'
import './styles.css'
import { readiness } from './lib/readiness'
import { Connection } from './components/Connection'
import { restoreDestination } from './lib/destination'

restoreDestination()
readiness.start()
window.addEventListener('pagehide', readiness.stop)
window.addEventListener('pageshow', event => { if (event.persisted) readiness.retry() })

const client = new QueryClient({ defaultOptions: { queries: {
  staleTime: 15000, retry: (count, error) => count < 1 && error instanceof ApiError && error.status >= 500,
  refetchOnWindowFocus: true,
}, mutations: { retry: false } } })
readiness.subscribe(() => { if (readiness.getSnapshot() === 'ready') void client.invalidateQueries() })
const router = createBrowserRouter([{ path: '*', element: <App /> }])
ReactDOM.createRoot(document.getElementById('root')!).render(<React.StrictMode><Connection /><QueryClientProvider client={client}><RouterProvider router={router} /></QueryClientProvider></React.StrictMode>)
