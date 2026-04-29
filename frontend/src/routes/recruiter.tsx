import { createFileRoute, Outlet, Link } from '@tanstack/react-router'

export const Route = createFileRoute('/recruiter')({
  component: RecruiterLayout,
})

function RecruiterLayout() {
  return (
    <div className="min-h-screen bg-gray-50">
      <nav className="bg-gray-900 text-white px-6 py-3 flex items-center gap-6 text-sm">
        <Link to="/recruiter/dashboard" className="font-bold text-base text-white">
          HireMatch
        </Link>
        <Link
          to="/recruiter/dashboard"
          className="hover:text-blue-300 [&.active]:text-blue-400"
        >
          Dashboard
        </Link>
        <Link
          to="/recruiter/req/new"
          className="hover:text-blue-300 [&.active]:text-blue-400"
        >
          New Req
        </Link>
        <Link
          to="/recruiter/network"
          className="hover:text-blue-300 [&.active]:text-blue-400"
        >
          Network
        </Link>
        <Link
          to="/recruiter/fingerprint"
          className="hover:text-blue-300 [&.active]:text-blue-400"
        >
          Fingerprint
        </Link>
      </nav>
      <main className="px-6 py-6 max-w-7xl mx-auto">
        <Outlet />
      </main>
    </div>
  )
}
