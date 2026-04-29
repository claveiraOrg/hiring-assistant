import { createFileRoute } from '@tanstack/react-router'
import { useMutation } from '@tanstack/react-query'
import { useState } from 'react'
import { api } from '../lib/api'

export const Route = createFileRoute('/recruiter/req/$reqId_/rerank')({
  component: Rerank,
})

function Rerank() {
  const { reqId } = Route.useParams()
  const [prompt, setPrompt] = useState('')
  const [success, setSuccess] = useState(false)

  const mutation = useMutation({
    mutationFn: (p: string) =>
      api.post(`req/${reqId}/rerank`, { json: { prompt: p } }).json(),
    onSuccess: () => {
      setSuccess(true)
      setPrompt('')
    },
  })

  return (
    <div className="max-w-2xl">
      <h1 className="text-xl font-bold text-gray-900 mb-2">Re-rank Candidates</h1>
      <p className="text-sm text-gray-500 mb-6">Req: {reqId}</p>

      {success && (
        <div className="mb-4 bg-green-50 border border-green-200 rounded p-3 text-green-700 text-sm">
          Re-ranking complete. Go back to see updated results.
        </div>
      )}

      <div className="bg-white border border-gray-200 rounded-lg p-6">
        <label className="block text-sm font-medium text-gray-700 mb-2">
          Natural language re-rank prompt
        </label>
        <textarea
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          rows={4}
          className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 mb-4"
          placeholder="e.g. Prioritise candidates with Rust experience and previous fintech exposure"
          disabled={mutation.isPending}
        />
        <div className="flex items-center gap-4">
          <button
            onClick={() => { if (prompt.trim()) mutation.mutate(prompt.trim()) }}
            disabled={!prompt.trim() || mutation.isPending}
            className="bg-indigo-600 text-white px-5 py-2 rounded-md text-sm font-medium hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
          >
            {mutation.isPending && (
              <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24" fill="none">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
              </svg>
            )}
            {mutation.isPending ? 'Re-ranking…' : 'Apply Re-rank'}
          </button>
          {mutation.isPending && (
            <span className="text-sm text-gray-500">This may take a few seconds…</span>
          )}
        </div>

        {mutation.isError && (
          <div className="mt-4 bg-red-50 border border-red-200 rounded p-3 text-red-700 text-sm">
            {(mutation.error as Error).message}
          </div>
        )}
      </div>
    </div>
  )
}
