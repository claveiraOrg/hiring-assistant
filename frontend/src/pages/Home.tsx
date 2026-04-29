import { Link } from '@tanstack/react-router'

export function HomePage() {
  return (
    <main className="container">
      <h1>hirematch</h1>
      <p className="subtitle">AI-powered hiring assistant — match the right candidates to every role.</p>
      <div className="portal-links">
        <Link to="/hiring" className="portal-link">Hiring Manager Portal</Link>
        <Link to="/candidate" className="portal-link secondary">Candidate Portal</Link>
      </div>
    </main>
  )
}
