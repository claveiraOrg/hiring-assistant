import { createFileRoute } from '@tanstack/react-router'
import { useQuery, useMutation } from '@tanstack/react-query'
import { useState } from 'react'
import { api } from '../lib/api'
import type { Candidate } from '../lib/types'

export const Route = createFileRoute('/recruiter/candidate/$candidateId')({
  component: CandidateDetail,
  errorComponent: ({ error }) => (
    <div className="bg-red-50 border border-red-200 rounded p-4 text-red-800">
      {(error as Error).message}
    </div>
  ),
})

function CandidateDetail() {
  const { candidateId } = Route.useParams()
  const [notes, setNotes] = useState('')
  const [notesSaved, setNotesSaved] = useState(false)

  const { data, isLoading, error } = useQuery({
    queryKey: ['candidate', candidateId],
    queryFn: () => api.get(`candidate/${candidateId}`).json<Candidate>(),
  })

  const saveNotesMutation = useMutation({
    mutationFn: (n: string) =>
      api.put(`candidate/${candidateId}/notes`, { json: { notes: n } }).json(),
    onSuccess: () => setNotesSaved(true),
  })

  if (isLoading) return <div className="text-gray-500 py-8">Loading candidate…</div>
  if (error) return (
    <div className="bg-red-50 border border-red-200 rounded p-4 text-red-800">
      {(error as Error).message}
    </div>
  )

  const candidate = data!

  return (
    <div className="max-w-4xl space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">{candidate.name}</h1>
        <div className="flex items-center gap-3 mt-2">
          <span className="text-lg font-semibold text-gray-700">Score: {candidate.score}/100</span>
          <span
            className={`text-xs font-medium px-2 py-1 rounded-full ${
              candidate.confidence === 'High'
                ? 'bg-green-100 text-green-700'
                : candidate.confidence === 'Med'
                  ? 'bg-yellow-100 text-yellow-700'
                  : 'bg-red-100 text-red-700'
            }`}
          >
            {candidate.confidence} confidence
          </span>
        </div>
      </div>

      <div className="bg-white border border-gray-200 rounded-lg p-5">
        <h2 className="font-semibold text-gray-900 mb-3">Evidence</h2>
        <ul className="space-y-2">
          {candidate.evidence.map((e, i) => (
            <li key={i} className="flex items-start gap-2 text-sm text-gray-700">
              <span className="text-green-500 mt-0.5">✓</span>
              {e}
            </li>
          ))}
        </ul>
      </div>

      {candidate.sub_scores && Object.keys(candidate.sub_scores).length > 0 && (
        <div className="bg-white border border-gray-200 rounded-lg p-5">
          <h2 className="font-semibold text-gray-900 mb-3">Score Breakdown</h2>
          <div className="space-y-3">
            {Object.entries(candidate.sub_scores).map(([k, v]) => (
              <div key={k} className="flex items-center gap-3">
                <span className="text-sm text-gray-600 w-40 flex-shrink-0">{k}</span>
                <div className="flex-1 h-2 bg-gray-200 rounded-full overflow-hidden">
                  <div className="h-full bg-blue-500 rounded-full" style={{ width: `${v}%` }} />
                </div>
                <span className="text-sm font-medium text-gray-700 w-8 text-right">{v}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {candidate.cv_url && (
        <div className="bg-white border border-gray-200 rounded-lg p-5">
          <h2 className="font-semibold text-gray-900 mb-3">CV Preview</h2>
          <iframe
            src={candidate.cv_url}
            className="w-full h-[600px] border border-gray-200 rounded"
            title="Candidate CV"
          />
        </div>
      )}

      <div className="bg-white border border-gray-200 rounded-lg p-5">
        <h2 className="font-semibold text-gray-900 mb-3">Recruiter Notes</h2>
        <textarea
          value={notes}
          onChange={(e) => { setNotes(e.target.value); setNotesSaved(false) }}
          onBlur={() => { if (notes.trim()) saveNotesMutation.mutate(notes) }}
          rows={4}
          className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 mb-3"
          placeholder="Add notes about this candidate…"
        />
        <div className="flex items-center gap-3">
          <button
            onClick={() => saveNotesMutation.mutate(notes)}
            disabled={saveNotesMutation.isPending}
            className="bg-blue-600 text-white px-4 py-1.5 rounded text-sm font-medium hover:bg-blue-700 disabled:opacity-50"
          >
            {saveNotesMutation.isPending ? 'Saving…' : 'Save Notes'}
          </button>
          {notesSaved && <span className="text-sm text-green-600">Saved</span>}
        </div>
      </div>
    </div>
  )
}
