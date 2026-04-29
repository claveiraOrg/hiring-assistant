import { useState } from 'react'
import { Link } from '@tanstack/react-router'
import { createCandidate, runMatch } from '../api'

interface MatchResult {
  candidate_id: string
  score: number
  reasoning: string
}

export function CandidatePage() {
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [jobId, setJobId] = useState('')
  const [resume, setResume] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [result, setResult] = useState<MatchResult | null>(null)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError(null)
    setResult(null)
    setLoading(true)
    try {
      const candidateRes = await createCandidate(name, email, resume)
      if (!candidateRes.ok) throw new Error(`Failed to submit: ${candidateRes.status}: ${await candidateRes.text()}`)
      const candidate = await candidateRes.json() as { id: string }

      const matchRes = await runMatch(jobId, [candidate.id])
      if (!matchRes.ok) throw new Error(`Matching failed: ${matchRes.status}: ${await matchRes.text()}`)
      const matchData = await matchRes.json() as { results?: { score: number; reasoning: string }[] }

      const top = (matchData.results ?? [])[0]
      if (!top) throw new Error('Match ran but returned no results. Verify the Job ID is correct.')

      setResult({ candidate_id: candidate.id, score: top.score, reasoning: top.reasoning })
      setName(''); setEmail(''); setJobId(''); setResume('')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error')
    } finally {
      setLoading(false)
    }
  }

  return (
    <main className="container">
      <div className="nav"><Link to="/">← Home</Link></div>
      <h1>Candidate Portal</h1>
      <p className="subtitle">Apply for a position and receive an instant AI match score.</p>

      <div className="alert alert-info">
        You will need a Job ID from the hiring manager.{' '}
        <Link to="/hiring">Visit the Hiring Portal</Link> to post a job and copy its ID.
      </div>

      <div className="card">
        <h2>Apply for a Position</h2>
        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label htmlFor="name">Full Name</label>
            <input id="name" type="text" value={name} onChange={e => setName(e.target.value)} placeholder="Jane Smith" required />
          </div>
          <div className="form-group">
            <label htmlFor="email">Email</label>
            <input id="email" type="email" value={email} onChange={e => setEmail(e.target.value)} placeholder="jane@example.com" required />
          </div>
          <div className="form-group">
            <label htmlFor="job-id">Job ID</label>
            <input id="job-id" type="text" value={jobId} onChange={e => setJobId(e.target.value)} placeholder="Paste the job UUID from the Hiring Manager Portal" required />
          </div>
          <div className="form-group">
            <label htmlFor="resume">Resume / Cover Letter</label>
            <textarea id="resume" rows={10} value={resume} onChange={e => setResume(e.target.value)} placeholder="Paste your resume text here..." required />
          </div>
          {error && <div className="alert alert-error">{error}</div>}
          <button type="submit" disabled={loading}>{loading ? 'Submitting…' : 'Submit Application'}</button>
        </form>
      </div>

      {result && (
        <div className="card">
          <h2>Your Match Result</h2>
          <div className="alert alert-success">Application submitted successfully.</div>
          <table>
            <tbody>
              <tr><th>Candidate ID</th><td>{result.candidate_id}</td></tr>
              <tr><th>Match Score</th><td><span className="score-badge">{result.score} / 100</span></td></tr>
              <tr><th>AI Reasoning</th><td className="reasoning-text">{result.reasoning}</td></tr>
            </tbody>
          </table>
        </div>
      )}
    </main>
  )
}
