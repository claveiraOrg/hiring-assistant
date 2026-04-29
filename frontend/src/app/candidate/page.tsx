"use client";

import { useState } from "react";

interface MatchResult {
  candidate_id: string;
  score: number;
  reasoning: string;
}

export default function CandidatePage() {
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [jobId, setJobId] = useState("");
  const [resume, setResume] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<MatchResult | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setResult(null);
    setLoading(true);

    try {
      // Step 1: Create candidate
      const candidateRes = await fetch("/api/hirematch/candidates", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name, email, resume_text: resume }),
      });
      if (!candidateRes.ok) {
        const msg = await candidateRes.text();
        throw new Error(`Failed to submit application: ${candidateRes.status}: ${msg}`);
      }
      const candidate = await candidateRes.json();

      // Step 2: Run AI match
      const matchRes = await fetch("/api/hirematch/match", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ job_id: jobId, candidate_ids: [candidate.id] }),
      });
      if (!matchRes.ok) {
        const msg = await matchRes.text();
        throw new Error(`Failed to run match: ${matchRes.status}: ${msg}`);
      }
      const matchData = await matchRes.json();
      const topResult = (matchData.results ?? [])[0];

      if (!topResult) {
        throw new Error("Match ran but returned no results. Verify the Job ID is correct.");
      }

      setResult({
        candidate_id: candidate.id,
        score: topResult.score,
        reasoning: topResult.reasoning,
      });

      setName("");
      setEmail("");
      setJobId("");
      setResume("");
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="container">
      <div className="nav">
        <a href="/">← Home</a>
      </div>
      <h1>Candidate Portal</h1>
      <p className="subtitle">Apply for a position and receive an instant AI match score.</p>

      <div className="alert alert-info">
        You will need a Job ID from the hiring manager. Visit the{" "}
        <a href="/hiring">Hiring Manager Portal</a> to post a job and copy its ID.
      </div>

      <div className="card">
        <h2>Apply for a Position</h2>
        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label htmlFor="name">Full Name</label>
            <input
              id="name"
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Jane Smith"
              required
            />
          </div>
          <div className="form-group">
            <label htmlFor="email">Email</label>
            <input
              id="email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="jane@example.com"
              required
            />
          </div>
          <div className="form-group">
            <label htmlFor="job-id">Job ID</label>
            <input
              id="job-id"
              type="text"
              value={jobId}
              onChange={(e) => setJobId(e.target.value)}
              placeholder="Paste the job UUID from the Hiring Manager Portal"
              required
            />
          </div>
          <div className="form-group">
            <label htmlFor="resume">Resume / Cover Letter</label>
            <textarea
              id="resume"
              rows={10}
              value={resume}
              onChange={(e) => setResume(e.target.value)}
              placeholder="Paste your resume text here. Include your experience, skills, and education."
              required
            />
          </div>
          {error && <div className="alert alert-error">{error}</div>}
          <button type="submit" disabled={loading}>
            {loading ? "Submitting…" : "Submit Application"}
          </button>
        </form>
      </div>

      {result && (
        <div className="card">
          <h2>Your Match Result</h2>
          <div className="alert alert-success">Application submitted successfully.</div>
          <table>
            <tbody>
              <tr>
                <th>Candidate ID</th>
                <td>{result.candidate_id}</td>
              </tr>
              <tr>
                <th>Match Score</th>
                <td>
                  <span className="score-badge">{result.score} / 100</span>
                </td>
              </tr>
              <tr>
                <th>AI Reasoning</th>
                <td className="reasoning-text">{result.reasoning}</td>
              </tr>
            </tbody>
          </table>
        </div>
      )}
    </main>
  );
}
