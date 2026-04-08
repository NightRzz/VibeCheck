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

    if (!url.trim()) {
      setError('Please enter a valid YouTube URL')
      return
    }

    setLoading(true)
    try {
      await onAdd(url.trim())
      setUrl('')
    } catch (err: any) {
      setError(err.message || 'Failed to track video')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="bg-gray-800 p-6 rounded-lg shadow-md border border-gray-700">
      <h3 className="text-xl font-bold mb-4 text-white flex items-center gap-2">
        <i className="icon-youtube text-red-500 text-2xl"></i> Track New Stream
      </h3>
      <form onSubmit={handleSubmit} className="flex gap-2">
        <input
          type="text"
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          placeholder="https://www.youtube.com/watch?v=..."
          className="flex-1 min-w-0 bg-gray-900 border border-gray-600 rounded-md px-4 py-2 text-white focus:outline-none focus:ring-2 focus:ring-blue-500 placeholder-gray-500"
          disabled={loading}
        />
        <button
          type="submit"
          disabled={loading || !url}
          className="shrink-0 bg-blue-600 hover:bg-blue-700 text-white font-medium py-2 px-6 rounded-md transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {loading ? 'Adding...' : 'Track'}
        </button>
      </form>
      {error && <p className="text-red-500 text-sm mt-2">{error}</p>}
    </div>
  )
}
