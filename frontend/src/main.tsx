import React from 'react'
import ReactDOM from 'react-dom/client'
import {
  RouterProvider,
  createRouter,
  createRoute,
  createRootRoute,
  Outlet,
} from '@tanstack/react-router'
import './styles.css'

import { HomePage } from './pages/Home'
import { HiringPage } from './pages/Hiring'
import { CandidatePage } from './pages/Candidate'

const rootRoute = createRootRoute({ component: () => <Outlet /> })

const indexRoute = createRoute({ getParentRoute: () => rootRoute, path: '/', component: HomePage })
const hiringRoute = createRoute({ getParentRoute: () => rootRoute, path: '/hiring', component: HiringPage })
const candidateRoute = createRoute({ getParentRoute: () => rootRoute, path: '/candidate', component: CandidatePage })

const routeTree = rootRoute.addChildren([indexRoute, hiringRoute, candidateRoute])

const router = createRouter({ routeTree })

declare module '@tanstack/react-router' {
  interface Register { router: typeof router }
}

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <RouterProvider router={router} />
  </React.StrictMode>,
)
