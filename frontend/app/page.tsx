import { Suspense } from 'react'
import { Dashboard } from '@/components/Dashboard'

export default async function Page() {
  const apiUrl = process.env.API_URL || process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
  const res = await fetch(`${apiUrl}/v1/tracked`, {
    cache: 'no-store',
  })
  const data = await res.json()

  return (
    <main className="container mx-auto p-4 max-w-7xl min-h-screen flex flex-col">
      <header className="mb-8 flex items-center gap-3">
        <i className="icon-pulse text-red-500 text-3xl"></i>
        <h1 className="text-4xl font-extrabold text-transparent bg-clip-text bg-gradient-to-r from-red-500 to-orange-500">
          VibeCheck Dashboard
        </h1>
      </header>
      <Suspense fallback={<div className="text-white">Loading dashboard...</div>}>
        <Dashboard initialVideos={data.items || []} />
      </Suspense>
    </main>
  )
}
