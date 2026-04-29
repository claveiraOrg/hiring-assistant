import { createFileRoute, Link } from '@tanstack/react-router'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  useReactTable,
  getCoreRowModel,
  getSortedRowModel,
  flexRender,
  createColumnHelper,
  type SortingState,
} from '@tanstack/react-table'
import { useState, useRef, useEffect } from 'react'
import { api } from '../lib/api'
import type { Candidate, RankingResponse } from '../lib/types'

export const Route = createFileRoute('/recruiter/req/$reqId')({
  component: ReqRanking,
  errorComponent: ({ error }) => (
    <div className="bg-red-50 border border-red-200 rounded p-4 text-red-800">
      Error loading ranking: {(error as Error).message}
    </div>
  ),
})

const REJECT_REASONS = [
  'Missing skill',
  'Too junior',
  'Too senior',
  'Wrong domain',
  'Salary mismatch',
] as const

type RejectReason = typeof REJECT_REASONS[number]

function ConfidenceBadge({ confidence }: { confidence: Candidate['confidence'] }) {
  const colors = {
    High: 'bg-green-100 text-green-700',
    Med: 'bg-yellow-100 text-yellow-700',
    Low: 'bg-red-100 text-red-700',
  }
  return (
    <span className={`inline-flex px-2 py-0.5 rounded-full text-xs font-medium ${colors[confidence]}`}>
      {confidence}
    </span>
  )
}

function ScoreTooltip({ subScores }: { subScores: Record<string, number> }) {
  return (
    <div className="absolute z-10 bottom-full left-1/2 -translate-x-1/2 mb-2 bg-gray-900 text-white text-xs rounded-lg p-3 shadow-lg min-w-40 pointer-events-none">
      <div className="font-medium mb-2">Score breakdown</div>
      {Object.entries(subScores).map(([k, v]) => (
        <div key={k} className="flex justify-between gap-4">
          <span className="text-gray-300">{k}</span>
          <span className="font-medium">{v}</span>
        </div>
      ))}
      <div className="absolute top-full left-1/2 -translate-x-1/2 w-0 h-0 border-l-4 border-r-4 border-t-4 border-l-transparent border-r-transparent border-t-gray-900" />
    </div>
  )
}

function ScoreCell({ score, subScores }: { score: number; subScores?: Record<string, number> }) {
  const [hovered, setHovered] = useState(false)
  return (
    <div
      className="relative inline-block"
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
    >
      <div className="flex items-center gap-2 cursor-help">
        <span className="font-bold text-gray-900 w-8 text-right">{score}</span>
        <div className="w-20 h-2 bg-gray-200 rounded-full overflow-hidden">
          <div
            className="h-full rounded-full bg-blue-500"
            style={{ width: `${score}%` }}
          />
        </div>
      </div>
      {hovered && subScores && Object.keys(subScores).length > 0 && (
        <ScoreTooltip subScores={subScores} />
      )}
    </div>
  )
}

function RejectButton({
  candidateId,
  reqId,
  onReject,
}: {
  candidateId: string
  reqId: string
  onReject: (candidateId: string, reason: RejectReason) => void
}) {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    function handler(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  void reqId

  return (
    <div ref={ref} className="relative">
      <button
        onClick={() => setOpen((v) => !v)}
        className="text-xs text-red-600 border border-red-200 rounded px-2 py-1 hover:bg-red-50"
      >
        Reject ▾
      </button>
      {open && (
        <div className="absolute right-0 top-full mt-1 bg-white border border-gray-200 rounded-lg shadow-lg z-20 min-w-44">
          {REJECT_REASONS.map((r) => (
            <button
              key={r}
              onClick={() => { onReject(candidateId, r); setOpen(false) }}
              className="block w-full text-left px-4 py-2 text-sm text-gray-700 hover:bg-gray-50"
            >
              {r}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}

const colHelper = createColumnHelper<Candidate>()

function ReqRanking() {
  const { reqId } = Route.useParams()
  const qc = useQueryClient()
  const [sorting, setSorting] = useState<SortingState>([])

  const { data, isLoading, error } = useQuery({
    queryKey: ['ranking', reqId],
    queryFn: () => api.get(`req/${reqId}/ranking`).json<RankingResponse>(),
    staleTime: 30_000,
  })

  const rejectMutation = useMutation({
    mutationFn: ({ candidateId, reason }: { candidateId: string; reason: RejectReason }) =>
      api.post(`req/${reqId}/reject/${candidateId}`, { json: { reason } }).json(),
    onMutate: async ({ candidateId }) => {
      await qc.cancelQueries({ queryKey: ['ranking', reqId] })
      const prev = qc.getQueryData<RankingResponse>(['ranking', reqId])
      qc.setQueryData<RankingResponse>(['ranking', reqId], (old) =>
        old ? { ...old, candidates: old.candidates.filter((c) => c.id !== candidateId) } : old,
      )
      return { prev }
    },
    onError: (_e, _v, ctx) => {
      if (ctx?.prev) qc.setQueryData(['ranking', reqId], ctx.prev)
    },
    onSettled: () => qc.invalidateQueries({ queryKey: ['ranking', reqId] }),
  })

  const columns = [
    colHelper.accessor('name', {
      header: 'Candidate',
      cell: (info) => (
        <Link
          to="/recruiter/candidate/$candidateId"
          params={{ candidateId: info.row.original.id }}
          className="font-medium text-blue-600 hover:underline"
        >
          {info.getValue()}
        </Link>
      ),
    }),
    colHelper.accessor('score', {
      header: 'Score',
      cell: (info) => (
        <ScoreCell score={info.getValue()} subScores={info.row.original.sub_scores} />
      ),
    }),
    colHelper.accessor('confidence', {
      header: 'Confidence',
      cell: (info) => <ConfidenceBadge confidence={info.getValue()} />,
    }),
    colHelper.accessor('evidence', {
      header: 'Evidence',
      enableSorting: false,
      cell: (info) => (
        <ul className="text-sm text-gray-600 space-y-0.5 list-disc list-inside">
          {info.getValue().slice(0, 3).map((e, i) => <li key={i}>{e}</li>)}
        </ul>
      ),
    }),
    colHelper.display({
      id: 'actions',
      header: '',
      cell: (info) => (
        <RejectButton
          candidateId={info.row.original.id}
          reqId={reqId}
          onReject={(cid, reason) => rejectMutation.mutate({ candidateId: cid, reason })}
        />
      ),
    }),
  ]

  const candidates = data?.candidates ?? []

  const table = useReactTable({
    data: candidates,
    columns,
    state: { sorting },
    onSortingChange: setSorting,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
  })

  if (isLoading) return <div className="text-gray-500 py-8">Loading ranking…</div>
  if (error) return (
    <div className="bg-red-50 border border-red-200 rounded p-4 text-red-800">
      {(error as Error).message}
    </div>
  )

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-xl font-bold text-gray-900">Ranked Candidates</h1>
          <p className="text-sm text-gray-500">Req: {reqId}</p>
        </div>
        <Link
          to="/recruiter/req/$reqId/rerank"
          params={{ reqId }}
          className="bg-indigo-600 text-white px-4 py-2 rounded text-sm font-medium hover:bg-indigo-700"
        >
          Re-rank
        </Link>
      </div>

      {candidates.length === 0 ? (
        <div className="bg-white border border-gray-200 rounded-lg p-12 text-center text-gray-500">
          No candidates ranked yet.
        </div>
      ) : (
        <div className="bg-white border border-gray-200 rounded-lg overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 border-b border-gray-200">
              {table.getHeaderGroups().map((hg) => (
                <tr key={hg.id}>
                  {hg.headers.map((h) => (
                    <th
                      key={h.id}
                      className="text-left px-4 py-3 font-semibold text-gray-700 select-none"
                    >
                      {h.isPlaceholder ? null : (
                        <div
                          className={h.column.getCanSort() ? 'cursor-pointer flex items-center gap-1' : ''}
                          onClick={h.column.getToggleSortingHandler()}
                        >
                          {flexRender(h.column.columnDef.header, h.getContext())}
                          {h.column.getIsSorted() === 'asc' && ' ↑'}
                          {h.column.getIsSorted() === 'desc' && ' ↓'}
                        </div>
                      )}
                    </th>
                  ))}
                </tr>
              ))}
            </thead>
            <tbody>
              {table.getRowModel().rows.map((row, idx) => (
                <tr
                  key={row.id}
                  className={`border-b border-gray-100 last:border-0 ${
                    idx < 3
                      ? 'bg-amber-50 border-l-4 border-l-amber-400'
                      : 'hover:bg-gray-50'
                  }`}
                >
                  {row.getVisibleCells().map((cell) => (
                    <td key={cell.id} className="px-4 py-3 align-top">
                      {flexRender(cell.column.columnDef.cell, cell.getContext())}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
          {candidates.length >= 3 && (
            <div className="px-4 py-2 bg-amber-50 border-t border-amber-200 text-xs text-amber-700 font-medium">
              Top 3 candidates highlighted
            </div>
          )}
        </div>
      )}
    </div>
  )
}
