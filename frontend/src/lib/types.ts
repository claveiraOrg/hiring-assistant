export interface Req {
  id: string
  title: string
  status: string
  candidate_count?: number
  created_at?: string
}

export interface Candidate {
  id: string
  name: string
  score: number
  confidence: 'High' | 'Med' | 'Low'
  evidence: string[]
  sub_scores?: Record<string, number>
  cv_url?: string
  domain?: string
  skills?: string[]
}

export interface RankingResponse {
  candidates: Candidate[]
}

export interface NetworkSuggestion {
  id: string
  skills: string[]
  domain: string
}

export interface FingerprintData {
  dimensions: FingerprintDimension[]
}

export interface FingerprintDimension {
  dimension: string
  value: string | number
}

export interface ConsentOrg {
  org_id: string
  org_name: string
  requested_at: string
  status: 'pending' | 'accepted' | 'declined'
}

export interface AccessLogEntry {
  recruiter_org: string
  viewed_at: string
  data_type: string
}

export interface CandidateProfile {
  skills: string[]
  domain: string
}
