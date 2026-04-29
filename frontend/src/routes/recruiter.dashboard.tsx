import { createFileRoute, Link } from '@tanstack/react-router'
import { useQuery } from '@tanstack/react-query'
import { api } from '../lib/api'
import type { Req } from '../lib/types'

export const Route = createFileRoute('/recruiter/dashboard')({
  component: Dashboard,
  errorComponent: ({ error }) => (
    <div className="bg-red-50 border border-red-200 rounded p-4 text-red-800">
      Failed to load dashboard: {(error as Error).message}
    </div>
  ),
})

function Dashboard() {
  const { data, isLoading, error } = useQuery({
    queryKey: ['reqs'],
    queryFn: () => api.get('req').json<Req[]>(),
  })

  if (isLoading) {
    return <div className="text-gray-500 py-8">Loading requisitions…</div>
  }

  if (error) {
    return (
      <div className="bg-red-50 border border-red-200 rounded p-4 text-red-800">
        Failed to load: {(error as Error).message}
      </div>
    )
  }

  const reqs = data ?? []

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Open Requisitions</h1>
        <Link
          to="/recruiter/req/new"
          className="bg-blue-600 text-white px-4 py-2 rounded text-sm font-medium hover:bg-blue-700"
        >
          + New Req
        </Link>
      </div>

      {reqs.length === 0 ? (
        <div className="bg-white border border-gray-200 rounded-lg p-12 text-center text-gray-500">
          No requisitions yet.{' '}
          <Link to="/recruiter/req/new" className="text-blue-600 hover:underline">
            Create one
          </Link>
          .
        </div>
      ) : (
        <div className="grid gap-4">
          {reqs.map((req) => (
            <Link
              key={req.id}
              to="/recruiter/req/$reqId"
              params={{ reqId: req.id }}
              className="block bg-white border border-gray-200 rounded-lg p-5 hover:border-blue-300 hover:shadow-sm transition-all"
            >
              <div className="flex items-start justify-between">
                <div>
                  <h2 className="font-semibold text-gray-900">{req.title}</h2>
                  <p className="text-sm text-gray-500 mt-1">ID: {req.id}</p>
                </div>
                <div className="flex items-center gap-3">
                  {req.candidate_count !== undefined && (
                    <span className="text-sm text-gray-600">
                      {req.candidate_count} candidate{req.candidate_count !== 1 ? 's' : ''}
                    </span>
                  )}
                  <span
                    className={`text-xs font-medium px-2 py-1 rounded-full ${
                      req.status === 'open'
                        ? 'bg-green-100 text-green-700'
                        : req.status === 'closed'
                          ? 'bg-gray-100 text-gray-600'
                          : 'bg-yellow-100 text-yellow-700'
                    }`}
                  >
                    {req.status}
                  </span>
                </div>
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  )
}
