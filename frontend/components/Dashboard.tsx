'use client'

import { useState, useCallback, useEffect } from 'react'
import { StatCards } from './StatCards'
import { VideoSidebar } from './VideoSidebar'
import { SentimentFeed } from './SentimentFeed'
import { VideoTracker } from './VideoTracker'

interface TrackedVideo {
  id: number
  video_id: string
  title: string
  is_active: boolean
  is_live?: boolean
  live_chat_id?: string | null
  message_count?: number
  average_score?: number | null
}

export function Dashboard({
  initialVideos,
}: {
  initialVideos: TrackedVideo[]
}) {
  const safeInitialVideos = Array.isArray(initialVideos) ? initialVideos : []
  const [videos, setVideos] = useState<TrackedVideo[]>(safeInitialVideos)
  const [selectedId, setSelectedId] = useState<string | null>(
    safeInitialVideos.length > 0 ? safeInitialVideos[0].video_id : null
  )

  const [stats, setStats] = useState({
    totalMsgs: 0,
    avgScore: 0,
    maxScore: 0,
    minScore: 0,
  })

  // Whenever selectedId changes, fetch authoritative historical stats immediately
  useEffect(() => {
    if (!selectedId) return

    let isCancelled = false

    const fetchStats = async () => {
      try {
        const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
        const res = await fetch(`${apiUrl}/v1/analytics/${selectedId}`, { cache: 'no-store' })
        if (res.ok && !isCancelled) {
          const data = await res.json()
          setStats({
            totalMsgs: data.total_messages || 0,
            avgScore: data.average_score || 0,
            maxScore: data.max_score || 0,
            minScore: data.min_score || 0,
          })
        }
      } catch (err) {
        console.error('Failed to fetch stats for video', selectedId, err)
      }
    }

    fetchStats()

    return () => {
      isCancelled = true
    }
  }, [selectedId])

  // Atomic stats update triggered ONLY by truly new live websocket messages
  const handleFeedStatsUpdate = useCallback((score: number) => {
    setStats((prev) => {
      const newTotal = prev.totalMsgs + 1
      const newAvg = (prev.avgScore * prev.totalMsgs + score) / newTotal
      return {
        totalMsgs: newTotal,
        avgScore: newAvg,
        maxScore: prev.totalMsgs === 0 ? score : Math.max(prev.maxScore, score),
        minScore: prev.totalMsgs === 0 ? score : Math.min(prev.minScore, score),
      }
    })

    // Also update sidebar message counter for the selected stream
    if (selectedId) {
      setVideos((prev) =>
        prev.map((v) =>
          v.video_id === selectedId
            ? { ...v, message_count: (v.message_count || 0) + 1 }
            : v
        )
      )
    }
  }, [selectedId])

  const handleAddVideo = async (videoUrlOrId: string) => {
    const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
    const res = await fetch(`${apiUrl}/v1/track`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ video: videoUrlOrId }),
    })

    if (!res.ok) {
      const errorData = await res.json().catch(() => ({}))
      throw new Error(errorData.detail || 'Failed to add video')
    }

    const newVideo = await res.json()
    setVideos((prev) => {
      const exists = prev.find((v) => v.video_id === newVideo.video_id)
      if (exists) return prev
      return [newVideo, ...prev]
    })

    // Switch to the newly added video
    setSelectedId(newVideo.video_id)
  }

  const handleSelectVideo = (id: string) => {
    if (selectedId === id) return
    setSelectedId(id)
  }

  const handleDeleteVideo = async (videoId: string) => {
    const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
    const res = await fetch(`${apiUrl}/v1/track/${videoId}`, {
      method: 'DELETE',
    })

    if (!res.ok) {
      throw new Error('Failed to delete stream')
    }

    setVideos((prev) => {
      const updated = prev.filter((v) => v.video_id !== videoId)
      if (selectedId === videoId) {
        setSelectedId(updated.length > 0 ? updated[0].video_id : null)
      }
      return updated
    })
  }

  const selectedVideo = videos.find((v) => v.video_id === selectedId)

  return (
    <div className="flex flex-col gap-6 flex-1">
      {/* Top Level Metric Cards */}
      <StatCards
        totalMsgs={stats.totalMsgs}
        avgScore={stats.avgScore}
        minScore={stats.minScore}
        maxScore={stats.maxScore}
      />

      {/* Main Workspace: Sidebar & Live Sentiment Stream */}
      <div className="flex flex-col lg:flex-row gap-6 flex-1 items-stretch">
        {/* Left Side: Tracker and Video List */}
        <div className="lg:w-80 flex flex-col gap-4 shrink-0">
          <VideoTracker onAdd={handleAddVideo} />
          <div className="flex-1 bg-zinc-900/60 border border-zinc-800/80 rounded-2xl overflow-hidden shadow-lg backdrop-blur-md min-h-[380px]">
            <VideoSidebar
              videos={videos}
              selectedId={selectedId}
              onSelect={handleSelectVideo}
              onDelete={handleDeleteVideo}
            />
          </div>
        </div>

        {/* Right Side: Active Sentiment Stream */}
        <div className="flex-1 flex flex-col min-w-0">
          <SentimentFeed
            videoId={selectedId}
            streamTitle={selectedVideo?.title}
            isLive={Boolean(selectedVideo?.is_live || selectedVideo?.live_chat_id)}
            onUpdateStats={handleFeedStatsUpdate}
          />
        </div>
      </div>
    </div>
  )
}
