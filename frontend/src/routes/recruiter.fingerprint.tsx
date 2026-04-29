import { createFileRoute } from '@tanstack/react-router'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '../lib/api'
import type { FingerprintData } from '../lib/types'

export const Route = createFileRoute('/recruiter/fingerprint')({
  component: Fingerprint,
})

function Fingerprint() {
  const qc = useQueryClient()

  const { data, isLoading, error } = useQuery({
    queryKey: ['fingerprint'],
    queryFn: () => api.get('fingerprint').json<FingerprintData>(),
  })

  const resetMutation = useMutation({
    mutationFn: (dimension: string) =>
      api.put(`fingerprint/${encodeURIComponent(dimension)}/reset`).json(),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['fingerprint'] }),
  })

  if (isLoading) return <div className="text-gray-500 py-8">Loading fingerprint…</div>
  if (error) return (
    <div className="bg-red-50 border border-red-200 rounded p-4 text-red-800">
      {(error as Error).message}
    </div>
  )

  const dims = data?.dimensions ?? []

  return (
    <div className="max-w-3xl">
      <h1 className="text-2xl font-bold text-gray-900 mb-2">Hiring Fingerprint</h1>
      <p className="text-sm text-gray-500 mb-6">
        Your latent hiring profile — biases and preferences inferred from past decisions.
      </p>

      {dims.length === 0 ? (
        <div className="bg-white border border-gray-200 rounded-lg p-12 text-center text-gray-500">
          Not enough hiring data to build a fingerprint yet.
        </div>
      ) : (
        <div className="bg-white border border-gray-200 rounded-lg divide-y divide-gray-100">
          {dims.map((dim) => (
            <div key={dim.dimension} className="flex items-center justify-between px-5 py-4">
              <div>
                <div className="text-sm font-medium text-gray-900 capitalize">
                  {dim.dimension.replace(/_/g, ' ')}
                </div>
                <div className="text-sm text-gray-500 mt-0.5">{String(dim.value)}</div>
              </div>
              <button
                onClick={() => resetMutation.mutate(dim.dimension)}
                disabled={resetMutation.isPending}
                className="text-xs text-red-600 border border-red-200 rounded px-3 py-1 hover:bg-red-50 disabled:opacity-50"
              >
                Reset
              </button>
            </div>
          ))}
        </div>
      )}

      {resetMutation.isError && (
        <div className="mt-4 bg-red-50 border border-red-200 rounded p-3 text-red-700 text-sm">
          Reset failed: {(resetMutation.error as Error).message}
        </div>
      )}
    </div>
  )
}
