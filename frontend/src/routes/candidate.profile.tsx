import { createFileRoute } from '@tanstack/react-router'
import { useQuery } from '@tanstack/react-query'
import { api } from '../lib/api'
import type { CandidateProfile } from '../lib/types'

export const Route = createFileRoute('/candidate/profile')({
  component: Profile,
})

function Profile() {
  const { data, isLoading, error } = useQuery({
    queryKey: ['candidate-profile'],
    queryFn: () => api.get('candidate/profile').json<CandidateProfile>(),
  })

  if (isLoading) return <div className="text-gray-500 py-8">Loading profile…</div>
  if (error) return (
    <div className="bg-red-50 border border-red-200 rounded p-4 text-red-800">
      {(error as Error).message}
    </div>
  )

  const profile = data!

  return (
    <div>
      <h1 className="text-2xl font-bold text-gray-900 mb-2">Your Profile</h1>
      <p className="text-sm text-gray-500 mb-6">
        This is how recruiters see you — skills and domain only.
      </p>

      <div className="bg-white border border-gray-200 rounded-lg p-6 space-y-5">
        <div>
          <h2 className="text-sm font-semibold text-gray-700 uppercase tracking-wide mb-2">Domain</h2>
          <p className="text-gray-900">{profile.domain || '—'}</p>
        </div>

        <div>
          <h2 className="text-sm font-semibold text-gray-700 uppercase tracking-wide mb-2">Skills</h2>
          {profile.skills && profile.skills.length > 0 ? (
            <div className="flex flex-wrap gap-2">
              {profile.skills.map((skill) => (
                <span
                  key={skill}
                  className="bg-blue-50 text-blue-700 text-sm px-3 py-1 rounded-full border border-blue-100"
                >
                  {skill}
                </span>
              ))}
            </div>
          ) : (
            <p className="text-gray-500 text-sm">No skills listed yet.</p>
          )}
        </div>
      </div>

      <p className="mt-4 text-xs text-gray-400">
        Scores and rankings are never shown to candidates.
      </p>
    </div>
  )
}
