const BASE_URL = (import.meta.env.VITE_HIREMATCH_API_URL as string) ?? 'http://localhost:8001'
const API_KEY = (import.meta.env.VITE_HIREMATCH_API_KEY as string) ?? 'dev-secret-key'

async function apiFetch(path: string, init?: RequestInit): Promise<Response> {
  return fetch(`${BASE_URL}/${path}`, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      'X-API-Key': API_KEY,
      ...(init?.headers ?? {}),
    },
  })
}

export async function createJob(title: string, description: string) {
  return apiFetch('jobs', { method: 'POST', body: JSON.stringify({ title, description }) })
}

export async function createCandidate(name: string, email: string, resume_text: string) {
  return apiFetch('candidates', { method: 'POST', body: JSON.stringify({ name, email, resume_text }) })
}

export async function runMatch(job_id: string, candidate_ids: string[]) {
  return apiFetch('match', { method: 'POST', body: JSON.stringify({ job_id, candidate_ids }) })
}

export async function getMatches(job_id: string) {
  return apiFetch(`matches/${job_id}`)
}
