import { createFileRoute, Outlet, Link } from '@tanstack/react-router'

export const Route = createFileRoute('/candidate')({
  component: CandidateLayout,
})

function CandidateLayout() {
  return (
    <div className="min-h-screen bg-white">
      <nav className="border-b border-gray-200 px-6 py-4 flex items-center gap-6">
        <span className="font-semibold text-gray-900 text-base">HireMatch</span>
        <Link
          to="/candidate/profile"
          className="text-sm text-gray-600 hover:text-gray-900 [&.active]:text-blue-600 [&.active]:font-medium"
        >
          Profile
        </Link>
        <Link
          to="/candidate/consent"
          className="text-sm text-gray-600 hover:text-gray-900 [&.active]:text-blue-600 [&.active]:font-medium"
        >
          Consent
        </Link>
        <Link
          to="/candidate/data"
          className="text-sm text-gray-600 hover:text-gray-900 [&.active]:text-blue-600 [&.active]:font-medium"
        >
          My Data
        </Link>
      </nav>
      <main className="max-w-2xl mx-auto px-6 py-8">
        <Outlet />
      </main>
    </div>
  )
}
