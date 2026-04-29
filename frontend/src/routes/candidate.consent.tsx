import { createFileRoute } from '@tanstack/react-router'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { api } from '../lib/api'
import type { ConsentOrg } from '../lib/types'

export const Route = createFileRoute('/candidate/consent')({
  component: Consent,
})

function ConfirmDialog({
  orgName,
  accept,
  onConfirm,
  onCancel,
}: {
  orgName: string
  accept: boolean
  onConfirm: () => void
  onCancel: () => void
}) {
  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50">
      <div className="bg-white rounded-xl shadow-xl p-6 max-w-sm w-full mx-4">
        <h3 className="font-semibold text-gray-900 mb-2">Confirm</h3>
        <p className="text-sm text-gray-600 mb-5">
          {accept
            ? `Allow ${orgName} to contact you?`
            : `Decline contact request from ${orgName}?`}
        </p>
        <div className="flex gap-3 justify-end">
          <button
            onClick={onCancel}
            className="px-4 py-2 text-sm text-gray-700 border border-gray-300 rounded hover:bg-gray-50"
          >
            Cancel
          </button>
          <button
            onClick={onConfirm}
            className={`px-4 py-2 text-sm text-white rounded font-medium ${
              accept ? 'bg-green-600 hover:bg-green-700' : 'bg-red-600 hover:bg-red-700'
            }`}
          >
            {accept ? 'Accept' : 'Decline'}
          </button>
        </div>
      </div>
    </div>
  )
}

function Consent() {
  const qc = useQueryClient()
  const [pending, setPending] = useState<{ org: ConsentOrg; accept: boolean } | null>(null)

  const { data, isLoading, error } = useQuery({
    queryKey: ['candidate-consent'],
    queryFn: () => api.get('candidate/consent').json<ConsentOrg[]>(),
  })

  const respondMutation = useMutation({
    mutationFn: ({ orgId, accept }: { orgId: string; accept: boolean }) =>
      api.post(`candidate/consent/${orgId}`, { json: { accept } }).json(),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['candidate-consent'] }),
  })

  if (isLoading) return <div className="text-gray-500 py-8">Loading consent requests…</div>
  if (error) return (
    <div className="bg-red-50 border border-red-200 rounded p-4 text-red-800">
      {(error as Error).message}
    </div>
  )

  const orgs = data ?? []
  const pending_requests = orgs.filter((o) => o.status === 'pending')
  const resolved = orgs.filter((o) => o.status !== 'pending')

  return (
    <div>
      {pending && (
        <ConfirmDialog
          orgName={pending.org.org_name}
          accept={pending.accept}
          onConfirm={() => {
            respondMutation.mutate({ orgId: pending.org.org_id, accept: pending.accept })
            setPending(null)
          }}
          onCancel={() => setPending(null)}
        />
      )}

      <h1 className="text-2xl font-bold text-gray-900 mb-2">Consent Requests</h1>
      <p className="text-sm text-gray-500 mb-6">
        These organisations have requested permission to contact you.
      </p>

      {pending_requests.length === 0 && resolved.length === 0 && (
        <div className="bg-gray-50 border border-gray-200 rounded-lg p-12 text-center text-gray-500">
          No consent requests yet.
        </div>
      )}

      {pending_requests.length > 0 && (
        <div className="space-y-3 mb-6">
          {pending_requests.map((org) => (
            <div key={org.org_id} className="bg-white border border-gray-200 rounded-lg p-5">
              <div className="flex items-start justify-between">
                <div>
                  <div className="font-medium text-gray-900">{org.org_name}</div>
                  <div className="text-xs text-gray-400 mt-0.5">
                    Requested {new Date(org.requested_at).toLocaleDateString()}
                  </div>
                </div>
                <div className="flex gap-2">
                  <button
                    onClick={() => setPending({ org, accept: false })}
                    className="text-sm border border-red-200 text-red-600 px-3 py-1.5 rounded hover:bg-red-50"
                  >
                    Decline
                  </button>
                  <button
                    onClick={() => setPending({ org, accept: true })}
                    className="text-sm bg-green-600 text-white px-3 py-1.5 rounded hover:bg-green-700 font-medium"
                  >
                    Accept
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {resolved.length > 0 && (
        <div>
          <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-3">
            Past decisions
          </h2>
          <div className="space-y-2">
            {resolved.map((org) => (
              <div
                key={org.org_id}
                className="flex items-center justify-between py-2 px-3 bg-gray-50 rounded text-sm"
              >
                <span className="text-gray-700">{org.org_name}</span>
                <span
                  className={`text-xs font-medium px-2 py-0.5 rounded-full ${
                    org.status === 'accepted'
                      ? 'bg-green-100 text-green-700'
                      : 'bg-red-100 text-red-700'
                  }`}
                >
                  {org.status}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
