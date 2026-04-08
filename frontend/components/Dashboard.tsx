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
}

export function Dashboard({
  initialVideos,
}: {
  initialVideos: TrackedVideo[]
}) {
  // Ensure we always have an array, even if the API fails or returns something unexpected
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

  // Whenever selectedId changes, let's also fetch its stats to avoid showing 0s on load
  useEffect(() => {
    if (!selectedId) return;

    const fetchStats = async () => {
      try {
        const res = await fetch(
          `${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/v1/analytics/${selectedId}`
        );
        if (res.ok) {
          const data = await res.json();
          setStats({
            totalMsgs: data.total_messages || 0,
            avgScore: data.average_score || 0,
            maxScore: data.max_score || 0,
            minScore: data.min_score || 0,
          });
        }
      } catch (err) {
        console.error("Failed to fetch initial stats", err);
      }
    };
    fetchStats();
  }, [selectedId]);

  // When a video changes, we only want to increment stats for that particular video.
  // We'll reset it to 0 only when changing, but the websocket might push updates simultaneously.
  // Using updateStatsAtomic ensures atomicity
  const updateStatsAtomic = useCallback((score: number, videoIdForScore: string) => {
    // Only update stats if the score belongs to the currently selected video
    setStats((prev: any) => {
      const newTotal = prev.totalMsgs + 1
      const newAvg = (prev.avgScore * prev.totalMsgs + score) / newTotal
      return {
        totalMsgs: newTotal,
        avgScore: newAvg,
        maxScore: prev.totalMsgs === 0 ? score : Math.max(prev.maxScore, score),
        minScore: prev.totalMsgs === 0 ? score : Math.min(prev.minScore, score),
      }
    })
  }, [])

  const handleFeedStatsUpdate = useCallback((score: number) => {
    if (!selectedId) return
    updateStatsAtomic(score, selectedId)
  }, [selectedId, updateStatsAtomic])

  const handleAddVideo = async (videoId: string) => {
    const res = await fetch(
      `${
        process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
      }/v1/track`,
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ video: videoId }),
      }
    )
    if (!res.ok) {
        const errorData = await res.json().catch(() => ({}));
        throw new Error(errorData.detail || 'Failed to add video');
    }
    const newVideo = await res.json()
    setVideos((prev: TrackedVideo[]) => {
      // Avoid duplicate entries in the sidebar if already present
      const exists = prev.find((v: TrackedVideo) => v.video_id === newVideo.video_id);
      if (exists) {
        return prev;
      }
      return [newVideo, ...prev];
    })
    
    // Switch to it immediately
    if (selectedId !== newVideo.video_id) {
        setSelectedId(newVideo.video_id)
        setStats({
            totalMsgs: 0,
            avgScore: 0,
            maxScore: 0,
            minScore: 0,
        })
    }
  }
  
  const handleSelectVideo = (id: string) => {
      if (selectedId === id) return; // prevent clearing stats if already selected

      setSelectedId(id)
      setStats({
          totalMsgs: 0,
          avgScore: 0,
          maxScore: 0,
          minScore: 0,
      })
  }

  const handleDeleteVideo = async (videoId: string) => {
    try {
      const res = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/v1/track/${videoId}`,
        {
          method: 'DELETE',
        }
      );
      if (!res.ok) {
        throw new Error('Failed to delete video');
      }
      
      setVideos((prev: TrackedVideo[]) => prev.filter((v: TrackedVideo) => v.video_id !== videoId));
      
      if (selectedId === videoId) {
        setSelectedId(videos.length > 1 ? videos.find((v: TrackedVideo) => v.video_id !== videoId)?.video_id || null : null);
        setStats({
          totalMsgs: 0,
          avgScore: 0,
          maxScore: 0,
          minScore: 0,
        });
      }
    } catch (err) {
      console.error("Error deleting video", err);
      alert("Failed to delete stream. Please try again.");
    }
  }

  return (
    <div className="flex flex-col lg:flex-row gap-6 flex-1">
      <div className="lg:w-1/4 flex flex-col gap-6">
        <VideoTracker onAdd={handleAddVideo} />
        <div className="flex-1 bg-gray-800 rounded-lg overflow-hidden border border-gray-700">
          <VideoSidebar
            videos={videos}
            selectedId={selectedId}
            onSelect={handleSelectVideo}
            onDelete={handleDeleteVideo}
          />
        </div>
      </div>

      <div className="lg:w-3/4 flex flex-col gap-6">
        <StatCards
          totalMsgs={stats.totalMsgs}
          avgScore={stats.avgScore}
          range={`${stats.minScore.toFixed(2)} to ${stats.maxScore.toFixed(2)}`}
        />
        <SentimentFeed
          videoId={selectedId}
          onUpdateStats={handleFeedStatsUpdate}
        />
      </div>
    </div>
  )
}
