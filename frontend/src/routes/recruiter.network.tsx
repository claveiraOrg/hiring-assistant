import { createFileRoute } from '@tanstack/react-router'
import { useQuery } from '@tanstack/react-query'
import { api } from '../lib/api'
import type { NetworkSuggestion } from '../lib/types'

export const Route = createFileRoute('/recruiter/network')({
  component: Network,
})

function Network() {
  const { data, isLoading, error } = useQuery({
    queryKey: ['network-suggestions'],
    queryFn: () => api.get('network/suggestions').json<NetworkSuggestion[]>(),
  })

  if (isLoading) return <div className="text-gray-500 py-8">Loading network…</div>
  if (error) return (
    <div className="bg-red-50 border border-red-200 rounded p-4 text-red-800">
      {(error as Error).message}
    </div>
  )

  const suggestions = (data ?? []).slice(0, 3)

  return (
    <div className="max-w-3xl">
      <h1 className="text-2xl font-bold text-gray-900 mb-2">Network</h1>
      <p className="text-sm text-gray-500 mb-6">
        Candidates from the consent-based network you may have missed.
      </p>

      {suggestions.length === 0 ? (
        <div className="bg-white border border-gray-200 rounded-lg p-12 text-center text-gray-500">
          No network suggestions available right now.
        </div>
      ) : (
        <div>
          <div className="mb-3 flex items-center gap-2">
            <span className="text-xs bg-blue-100 text-blue-700 px-2 py-1 rounded-full font-medium">
              From network (consent-based)
            </span>
          </div>
          <div className="grid gap-4">
            {suggestions.map((s) => (
              <div
                key={s.id}
                className="bg-white border border-gray-200 rounded-lg p-5"
              >
                <div className="text-xs text-gray-400 uppercase tracking-wide mb-2 font-medium">
                  Anonymous profile
                </div>
                <div className="mb-2">
                  <span className="text-sm font-medium text-gray-700">Domain:</span>{' '}
                  <span className="text-sm text-gray-900">{s.domain}</span>
                </div>
                <div>
                  <span className="text-sm font-medium text-gray-700">Skills:</span>
                  <div className="flex flex-wrap gap-1 mt-1">
                    {s.skills.map((skill) => (
                      <span
                        key={skill}
                        className="text-xs bg-gray-100 text-gray-700 px-2 py-0.5 rounded"
                      >
                        {skill}
                      </span>
                    ))}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
