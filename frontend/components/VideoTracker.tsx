'use client'

import { useState } from 'react'

interface VideoTrackerProps {
  onAdd: (videoId: string) => Promise<void>
}

export function VideoTracker({ onAdd }: VideoTrackerProps) {
  const [url, setUrl] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')

    const trimmed = url.trim()
    if (!trimmed) {
      setError('Please paste a YouTube Live URL or video ID.')
      return
    }

    setLoading(true)
    try {
      await onAdd(trimmed)
      setUrl('')
    } catch (err: any) {
      setError(err.message || 'Failed to initialize stream tracking.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="bg-zinc-900/60 border border-zinc-800/80 rounded-2xl p-4 shadow-lg backdrop-blur-md">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-xs font-semibold uppercase tracking-wider text-zinc-300 flex items-center gap-2">
          <svg className="w-4 h-4 text-rose-500" fill="currentColor" viewBox="0 0 24 24">
            <path d="M19.615 3.184c-3.604-.246-11.631-.245-15.23 0-3.897.266-4.356 2.62-4.385 8.816.029 6.185.484 8.549 4.385 8.816 3.6.245 11.626.246 15.23 0 3.897-.266 4.356-2.62 4.385-8.816-.029-6.185-.484-8.549-4.385-8.816zm-10.615 12.816v-8l8 3.993-8 4.007z" />
          </svg>
          Track Stream or Chat
        </h3>
        <span className="text-[10px] text-zinc-500 font-mono">Live Ingestion</span>
      </div>

      <form onSubmit={handleSubmit} className="flex flex-col gap-2">
        <div className="relative flex items-center">
          <input
            type="text"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            placeholder="https://youtube.com/watch?v=... or /live/..."
            className="w-full bg-zinc-950/80 border border-zinc-800 rounded-xl px-3.5 py-2 text-xs text-zinc-200 placeholder-zinc-500 focus:outline-none focus:ring-2 focus:ring-indigo-500/50 focus:border-indigo-500 transition-all font-mono"
            disabled={loading}
          />
        </div>

        <button
          type="submit"
          disabled={loading || !url.trim()}
          className="w-full bg-indigo-600 hover:bg-indigo-500 text-white font-medium py-2 px-4 rounded-xl text-xs transition-all shadow-md shadow-indigo-950/30 flex items-center justify-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer"
        >
          {loading ? (
            <>
              <div className="w-3.5 h-3.5 border-2 border-white/30 border-t-white rounded-full animate-spin"></div>
              <span>Connecting Stream...</span>
            </>
          ) : (
            <>
              <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
              </svg>
              <span>Add Stream</span>
            </>
          )}
        </button>
      </form>

      {error && (
        <div className="mt-2.5 p-2 rounded-lg bg-rose-500/10 border border-rose-500/20 text-rose-400 text-[11px] leading-tight">
          {error}
        </div>
      )}
    </div>
  )
}
