import { createFileRoute, useNavigate } from '@tanstack/react-router'
import { useForm } from '@tanstack/react-form'
import { useRef, useState } from 'react'
import { api } from '../lib/api'

export const Route = createFileRoute('/recruiter/req/new')({
  component: NewReq,
})

const MAX_FILES = 50
const MAX_SIZE_MB = 5
const ALLOWED_TYPES = ['application/pdf', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document']

function NewReq() {
  const navigate = useNavigate()
  const [files, setFiles] = useState<File[]>([])
  const [dragOver, setDragOver] = useState(false)
  const [submitError, setSubmitError] = useState<string | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const form = useForm({
    defaultValues: { jd: '', intent: '' },
    onSubmit: async ({ value }) => {
      setSubmitError(null)
      try {
        const req = await api.post('req', { json: { jd: value.jd, intent: value.intent } }).json<{ id: string }>()
        if (files.length > 0) {
          const formData = new FormData()
          files.forEach((f) => formData.append('files', f))
          await api.post(`req/${req.id}/upload`, { body: formData, headers: {} })
        }
        void navigate({ to: '/recruiter/req/$reqId', params: { reqId: req.id } })
      } catch (e) {
        setSubmitError((e as Error).message)
      }
    },
  })

  function addFiles(incoming: FileList | File[]) {
    const arr = Array.from(incoming)
    const valid = arr.filter((f) => {
      if (!ALLOWED_TYPES.includes(f.type)) return false
      if (f.size > MAX_SIZE_MB * 1024 * 1024) return false
      return true
    })
    setFiles((prev) => {
      const combined = [...prev, ...valid]
      return combined.slice(0, MAX_FILES)
    })
  }

  function removeFile(idx: number) {
    setFiles((prev) => prev.filter((_, i) => i !== idx))
  }

  return (
    <div className="max-w-3xl">
      <h1 className="text-2xl font-bold text-gray-900 mb-6">New Requisition</h1>

      <form
        onSubmit={(e) => {
          e.preventDefault()
          void form.handleSubmit()
        }}
        className="space-y-6"
      >
        <form.Field
          name="jd"
          children={(field) => (
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Job Description
              </label>
              <textarea
                value={field.state.value}
                onChange={(e) => field.handleChange(e.target.value)}
                onBlur={field.handleBlur}
                rows={8}
                className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 font-mono"
                placeholder="Paste the full job description here…"
                required
              />
            </div>
          )}
        />

        <form.Field
          name="intent"
          children={(field) => (
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Baseline Intent
              </label>
              <textarea
                value={field.state.value}
                onChange={(e) => field.handleChange(e.target.value)}
                onBlur={field.handleBlur}
                rows={3}
                className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                placeholder="What does a strong hire look like? Any deal-breakers?"
              />
            </div>
          )}
        />

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            CV Upload (PDF / DOCX, max {MAX_SIZE_MB} MB each, up to {MAX_FILES} files)
          </label>
          <div
            className={`border-2 border-dashed rounded-lg p-8 text-center cursor-pointer transition-colors ${
              dragOver ? 'border-blue-500 bg-blue-50' : 'border-gray-300 hover:border-gray-400'
            }`}
            onDragOver={(e) => { e.preventDefault(); setDragOver(true) }}
            onDragLeave={() => setDragOver(false)}
            onDrop={(e) => {
              e.preventDefault()
              setDragOver(false)
              addFiles(e.dataTransfer.files)
            }}
            onClick={() => fileInputRef.current?.click()}
          >
            <p className="text-gray-500 text-sm">
              Drag & drop CVs here, or <span className="text-blue-600 font-medium">browse</span>
            </p>
            <input
              ref={fileInputRef}
              type="file"
              multiple
              accept=".pdf,.docx"
              className="hidden"
              onChange={(e) => e.target.files && addFiles(e.target.files)}
            />
          </div>

          {files.length > 0 && (
            <ul className="mt-3 space-y-1">
              {files.map((f, i) => (
                <li key={i} className="flex items-center justify-between text-sm bg-gray-50 px-3 py-1.5 rounded">
                  <span className="text-gray-700 truncate">{f.name}</span>
                  <button
                    type="button"
                    onClick={() => removeFile(i)}
                    className="text-red-500 hover:text-red-700 ml-2 text-xs flex-shrink-0"
                  >
                    Remove
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>

        {submitError && (
          <div className="bg-red-50 border border-red-200 rounded p-3 text-red-700 text-sm">
            {submitError}
          </div>
        )}

        <form.Subscribe
          selector={(state) => [state.canSubmit, state.isSubmitting]}
          children={([canSubmit, isSubmitting]) => (
            <button
              type="submit"
              disabled={!canSubmit || (isSubmitting as boolean)}
              className="bg-blue-600 text-white px-6 py-2 rounded-md font-medium text-sm hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {(isSubmitting as boolean) ? 'Creating…' : 'Create Requisition'}
            </button>
          )}
        />
      </form>
    </div>
  )
}
