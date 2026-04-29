import { createFileRoute } from '@tanstack/react-router'
import { useState } from 'react'
import { api } from '../lib/api'

export const Route = createFileRoute('/candidate/login')({
  component: CandidateLogin,
})

function CandidateLogin() {
  const [email, setEmail] = useState('')
  const [loading, setLoading] = useState(false)
  const [sent, setSent] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setLoading(true)
    setError(null)
    try {
      await api.post('candidate/magic-link', { json: { email } }).json()
      setSent(true)
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setLoading(false)
    }
  }

  if (sent) {
    return (
      <div className="text-center py-12">
        <div className="text-4xl mb-4">✉️</div>
        <h1 className="text-xl font-semibold text-gray-900 mb-2">Check your inbox</h1>
        <p className="text-gray-500 text-sm">
          We sent a magic link to <strong>{email}</strong>. Click it to sign in.
        </p>
      </div>
    )
  }

  return (
    <div>
      <h1 className="text-2xl font-bold text-gray-900 mb-2">Sign in</h1>
      <p className="text-gray-500 text-sm mb-8">
        Enter your email and we'll send you a magic link.
      </p>

      <form onSubmit={(e) => void handleSubmit(e)} className="space-y-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Email address</label>
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
            autoFocus
            placeholder="you@example.com"
            className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>

        {error && (
          <div className="bg-red-50 border border-red-200 rounded p-3 text-red-700 text-sm">
            {error}
          </div>
        )}

        <button
          type="submit"
          disabled={loading || !email}
          className="w-full bg-blue-600 text-white py-2 rounded-md font-medium text-sm hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {loading ? 'Sending…' : 'Send magic link'}
        </button>
      </form>
    </div>
  )
}
