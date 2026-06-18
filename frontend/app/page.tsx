import { Suspense } from 'react'
import { Dashboard } from '@/components/Dashboard'

export const dynamic = 'force-dynamic'

export default async function Page() {
  const apiUrl = process.env.API_URL || process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
  let initialVideos = []

  try {
    const res = await fetch(`${apiUrl}/v1/tracked`, {
      cache: 'no-store',
    })
    if (res.ok) {
      const data = await res.json()
      initialVideos = data.items || []
    }
  } catch (err) {
    console.error('Failed to fetch tracked videos on SSR', err)
  }

  return (
    <div className="min-h-screen bg-[#090D14] text-zinc-100 flex flex-col font-sans selection:bg-indigo-500/30 selection:text-indigo-200">
      {/* Top Engineering Nav Bar */}
      <header className="border-b border-zinc-800/80 bg-zinc-950/60 backdrop-blur-xl sticky top-0 z-50">
        <div className="container mx-auto px-4 lg:px-8 max-w-7xl h-16 flex items-center justify-between gap-4">
          {/* Brand Logo & Architecture */}
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center shadow-lg shadow-indigo-500/20">
              <svg className="w-5 h-5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
              </svg>
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="text-base font-bold tracking-tight text-white">VibeCheck</span>
                <span className="text-[10px] uppercase font-mono px-1.5 py-0.2 rounded bg-indigo-500/10 text-indigo-400 border border-indigo-500/20 font-semibold">
                  RoBERTa ONNX
                </span>
              </div>
              <p className="text-[11px] text-zinc-500 hidden sm:block">
                Real-Time Streaming Sentiment Intelligence
              </p>
            </div>
          </div>

          {/* System Telemetry & Quick Action Links */}
          <div className="flex items-center gap-2.5">
            {/* MLflow Link */}
            <a
              href="http://localhost:5000"
              target="_blank"
              rel="noreferrer"
              className="hidden sm:inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-medium bg-zinc-900 border border-zinc-800 text-zinc-300 hover:text-white hover:border-zinc-700 hover:bg-zinc-850 transition-all shadow-sm"
              title="Open MLflow Experiment Tracking Dashboard"
            >
              <span className="w-2 h-2 rounded-full bg-blue-400"></span>
              <span>MLflow Tracking</span>
            </a>

            {/* Evidently AI Drift Report */}
            <a
              href="http://localhost:8000/v1/ml/drift-report"
              target="_blank"
              rel="noreferrer"
              className="hidden md:inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-medium bg-zinc-900 border border-zinc-800 text-zinc-300 hover:text-white hover:border-zinc-700 hover:bg-zinc-850 transition-all shadow-sm"
              title="Open Evidently AI Data & Prediction Drift Report"
            >
              <span className="w-2 h-2 rounded-full bg-purple-400"></span>
              <span>Drift Report</span>
            </a>

            {/* API Docs */}
            <a
              href="http://localhost:8000/docs"
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-medium bg-indigo-600/10 border border-indigo-500/20 text-indigo-400 hover:bg-indigo-600/20 hover:border-indigo-500/30 transition-all"
            >
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400"></span>
              <span>API Swagger</span>
            </a>
          </div>
        </div>
      </header>

      {/* Main Container */}
      <main className="container mx-auto px-4 lg:px-8 max-w-7xl py-6 flex-1 flex flex-col">
        <Suspense
          fallback={
            <div className="flex-1 flex flex-col items-center justify-center min-h-[400px] text-zinc-500 gap-3">
              <div className="w-8 h-8 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin"></div>
              <p className="text-xs">Initializing dashboard workspace...</p>
            </div>
          }
        >
          <Dashboard initialVideos={initialVideos} />
        </Suspense>
      </main>

      {/* Subtle Engineering Footer */}
      <footer className="border-t border-zinc-900 py-3 text-center text-zinc-600 text-xs font-mono">
        VibeCheck MLOps Pipeline &bull; ONNX Runtime CPU Inference &bull; Apache Kafka &bull; PostgreSQL
      </footer>
    </div>
  )
}
