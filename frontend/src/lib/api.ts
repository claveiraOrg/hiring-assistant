import ky from 'ky'

export const api = ky.create({
  prefixUrl: import.meta.env.VITE_API_URL ?? 'http://178.104.211.230:8001',
  credentials: 'include',
  headers: {
    'Content-Type': 'application/json',
  },
})
