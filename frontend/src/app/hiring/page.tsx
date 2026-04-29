"use client";

import { useState } from "react";

interface MatchResult {
  candidate_id: string;
  name: string;
  email: string;
  score: number;
  reasoning: string;
}

export default function HiringPage() {
  // Post a Job
  const [jobTitle, setJobTitle] = useState("");
  const [jobDesc, setJobDesc] = useState("");
  const [jobId, setJobId] = useState<string | null>(null);
  const [jobLoading, setJobLoading] = useState(false);
  const [jobError, setJobError] = useState<string | null>(null);

  // Run AI Match
  const [matchJobId, setMatchJobId] = useState("");
  const [candidateIds, setCandidateIds] = useState("");
  const [matchLoading, setMatchLoading] = useState(false);
  const [matchError, setMatchError] = useState<string | null>(null);
  const [results, setResults] = useState<MatchResult[] | null>(null);

  async function handlePostJob(e: React.FormEvent) {
    e.preventDefault();
    setJobError(null);
    setJobId(null);
    setJobLoading(true);
    try {
      const res = await fetch("/api/hirematch/jobs", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title: jobTitle, description: jobDesc }),
      });
      if (!res.ok) {
        const msg = await res.text();
        throw new Error(`${res.status}: ${msg}`);
      }
      const data = await res.json();
      setJobId(data.id);
      setMatchJobId(data.id);
      setJobTitle("");
      setJobDesc("");
    } catch (err: unknown) {
      setJobError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setJobLoading(false);
    }
  }

  async function handleRunMatch(e: React.FormEvent) {
    e.preventDefault();
    setMatchError(null);
    setResults(null);
    setMatchLoading(true);
    try {
      const ids = candidateIds.split(",").map((s) => s.trim()).filter(Boolean);
      const res = await fetch("/api/hirematch/match", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ job_id: matchJobId, candidate_ids: ids }),
      });
      if (!res.ok) {
        const msg = await res.text();
        throw new Error(`${res.status}: ${msg}`);
      }
      const data = await res.json();

      // Fetch candidate names/emails from ranked matches endpoint
      const rankedRes = await fetch(`/api/hirematch/matches/${matchJobId}`);
      if (rankedRes.ok) {
        const ranked = await rankedRes.json();
        setResults(ranked.candidates ?? []);
      } else {
        // Fall back to match results without name/email
        setResults(
          (data.results ?? []).map((r: MatchResult) => ({
            ...r,
            name: r.name ?? "—",
            email: r.email ?? "—",
          }))
        );
      }
    } catch (err: unknown) {
      setMatchError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setMatchLoading(false);
    }
  }

  return (
    <main className="container">
      <div className="nav">
        <a href="/">← Home</a>
      </div>
      <h1>Hiring Manager Portal</h1>
      <p className="subtitle">Post jobs and run AI matching to rank candidates.</p>

      {/* Post a Job */}
      <div className="card">
        <h2>Post a Job</h2>
        <form onSubmit={handlePostJob}>
          <div className="form-group">
            <label htmlFor="job-title">Job Title</label>
            <input
              id="job-title"
              type="text"
              value={jobTitle}
              onChange={(e) => setJobTitle(e.target.value)}
              placeholder="e.g. Senior Software Engineer"
              required
            />
          </div>
          <div className="form-group">
            <label htmlFor="job-desc">Job Description</label>
            <textarea
              id="job-desc"
              rows={5}
              value={jobDesc}
              onChange={(e) => setJobDesc(e.target.value)}
              placeholder="Describe the role, responsibilities, and requirements..."
              required
            />
          </div>
          {jobError && <div className="alert alert-error">{jobError}</div>}
          {jobId && (
            <div className="alert alert-success">
              Job created. ID: <strong>{jobId}</strong>
            </div>
          )}
          <button type="submit" disabled={jobLoading}>
            {jobLoading ? "Posting…" : "Post Job"}
          </button>
        </form>
      </div>

      {/* Run AI Match */}
      <div className="card">
        <h2>Run AI Match</h2>
        <form onSubmit={handleRunMatch}>
          <div className="form-group">
            <label htmlFor="match-job-id">Job ID</label>
            <input
              id="match-job-id"
              type="text"
              value={matchJobId}
              onChange={(e) => setMatchJobId(e.target.value)}
              placeholder="Paste job UUID"
              required
            />
          </div>
          <div className="form-group">
            <label htmlFor="candidate-ids">Candidate IDs (comma-separated)</label>
            <input
              id="candidate-ids"
              type="text"
              value={candidateIds}
              onChange={(e) => setCandidateIds(e.target.value)}
              placeholder="uuid1, uuid2, uuid3"
              required
            />
          </div>
          {matchError && <div className="alert alert-error">{matchError}</div>}
          <button type="submit" disabled={matchLoading}>
            {matchLoading ? "Matching…" : "Run AI Match"}
          </button>
        </form>
      </div>

      {/* Ranked Results */}
      {results !== null && (
        <div className="card">
          <h2>Ranked Results</h2>
          {results.length === 0 ? (
            <p>No results returned. Make sure the candidate IDs are valid.</p>
          ) : (
            <table>
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Email</th>
                  <th>Score</th>
                  <th>AI Reasoning</th>
                </tr>
              </thead>
              <tbody>
                {results.map((r) => (
                  <tr key={r.candidate_id}>
                    <td>{r.name}</td>
                    <td>{r.email}</td>
                    <td>
                      <span className="score-badge">{r.score}</span>
                    </td>
                    <td className="reasoning-text">{r.reasoning}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}
    </main>
  );
}
