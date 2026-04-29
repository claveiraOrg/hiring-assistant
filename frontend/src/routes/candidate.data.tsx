import { createFileRoute } from '@tanstack/react-router'
import { useQuery, useMutation } from '@tanstack/react-query'
import { useState } from 'react'
import { api } from '../lib/api'
import type { AccessLogEntry } from '../lib/types'

export const Route = createFileRoute('/candidate/data')({
  component: CandidateData,
})

type ConfirmTarget = 'cv' | 'network' | null

function CandidateData() {
  const [confirmTarget, setConfirmTarget] = useState<ConfirmTarget>(null)
  const [deleteResult, setDeleteResult] = useState<{ target: string; ok: boolean } | null>(null)
  const [exportLoading, setExportLoading] = useState(false)
  const [exportError, setExportError] = useState<string | null>(null)

  const { data: accessLog, isLoading: logLoading } = useQuery({
    queryKey: ['access-log'],
    queryFn: () => api.get('candidate/access-log').json<AccessLogEntry[]>(),
  })

  const deleteMutation = useMutation({
    mutationFn: (target: 'cv' | 'network') =>
      api.post('candidate/delete', { json: { target } }).json(),
    onSuccess: (_data, target) => {
      setDeleteResult({ target, ok: true })
      setConfirmTarget(null)
    },
    onError: (_err, target) => {
      setDeleteResult({ target, ok: false })
      setConfirmTarget(null)
    },
  })

  async function handleExport() {
    setExportLoading(true)
    setExportError(null)
    try {
      const blob = await api.get('candidate/export').blob()
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = 'my-hirematch-data.json'
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      URL.revokeObjectURL(url)
    } catch (e) {
      setExportError((e as Error).message)
    } finally {
      setExportLoading(false)
    }
  }

  return (
    <div>
      {confirmTarget && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50">
          <div className="bg-white rounded-xl shadow-xl p-6 max-w-sm w-full mx-4">
            <h3 className="font-semibold text-gray-900 mb-2">Confirm deletion</h3>
            <p className="text-sm text-gray-600 mb-5">
              {confirmTarget === 'cv'
                ? 'Are you sure you want to permanently delete your CV from HireMatch? This cannot be undone.'
                : 'Are you sure you want to remove yourself from the consent network? This cannot be undone.'}
            </p>
            <div className="flex gap-3 justify-end">
              <button
                onClick={() => setConfirmTarget(null)}
                className="px-4 py-2 text-sm text-gray-700 border border-gray-300 rounded hover:bg-gray-50"
              >
                Cancel
              </button>
              <button
                onClick={() => deleteMutation.mutate(confirmTarget)}
                disabled={deleteMutation.isPending}
                className="px-4 py-2 text-sm text-white bg-red-600 hover:bg-red-700 rounded font-medium disabled:opacity-50"
              >
                {deleteMutation.isPending ? 'Deleting…' : 'Delete'}
              </button>
            </div>
          </div>
        </div>
      )}

      <h1 className="text-2xl font-bold text-gray-900 mb-2">My Data</h1>
      <p className="text-sm text-gray-500 mb-6">
        GDPR controls — manage your data and privacy.
      </p>

      {deleteResult && (
        <div
          className={`mb-4 p-3 rounded border text-sm ${
            deleteResult.ok
              ? 'bg-green-50 border-green-200 text-green-700'
              : 'bg-red-50 border-red-200 text-red-700'
          }`}
        >
          {deleteResult.ok
            ? `Successfully deleted: ${deleteResult.target}`
            : `Failed to delete: ${deleteResult.target}`}
        </div>
      )}

      <div className="space-y-4 mb-10">
        <div className="bg-white border border-gray-200 rounded-lg p-5 flex items-center justify-between">
          <div>
            <div className="font-medium text-gray-900">Delete CV</div>
            <div className="text-sm text-gray-500">Remove your CV from HireMatch permanently</div>
          </div>
          <button
            onClick={() => setConfirmTarget('cv')}
            className="text-sm text-red-600 border border-red-200 px-4 py-2 rounded hover:bg-red-50 font-medium"
          >
            Delete CV
          </button>
        </div>

        <div className="bg-white border border-gray-200 rounded-lg p-5 flex items-center justify-between">
          <div>
            <div className="font-medium text-gray-900">Remove from Network</div>
            <div className="text-sm text-gray-500">Opt out of the consent-based candidate network</div>
          </div>
          <button
            onClick={() => setConfirmTarget('network')}
            className="text-sm text-red-600 border border-red-200 px-4 py-2 rounded hover:bg-red-50 font-medium"
          >
            Remove
          </button>
        </div>

        <div className="bg-white border border-gray-200 rounded-lg p-5 flex items-center justify-between">
          <div>
            <div className="font-medium text-gray-900">Export My Data</div>
            <div className="text-sm text-gray-500">Download everything HireMatch holds about you</div>
          </div>
          <button
            onClick={() => void handleExport()}
            disabled={exportLoading}
            className="text-sm text-blue-600 border border-blue-200 px-4 py-2 rounded hover:bg-blue-50 font-medium disabled:opacity-50"
          >
            {exportLoading ? 'Exporting…' : 'Export'}
          </button>
        </div>
        {exportError && (
          <p className="text-red-600 text-sm">{exportError}</p>
        )}
      </div>

      <div>
        <h2 className="text-lg font-semibold text-gray-900 mb-3">Access Log</h2>
        <p className="text-sm text-gray-500 mb-4">
          Record of when recruiters viewed your data.
        </p>

        {logLoading ? (
          <div className="text-gray-500 text-sm">Loading access log…</div>
        ) : !accessLog || accessLog.length === 0 ? (
          <div className="bg-gray-50 border border-gray-200 rounded-lg p-8 text-center text-gray-500 text-sm">
            No access events recorded yet.
          </div>
        ) : (
          <div className="bg-white border border-gray-200 rounded-lg divide-y divide-gray-100">
            {accessLog.map((entry, i) => (
              <div key={i} className="px-5 py-3 flex items-center justify-between text-sm">
                <div>
                  <span className="font-medium text-gray-900">{entry.recruiter_org}</span>
                  <span className="text-gray-400 ml-2">· {entry.data_type}</span>
                </div>
                <span className="text-gray-500 text-xs">
                  {new Date(entry.viewed_at).toLocaleString()}
                </span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
