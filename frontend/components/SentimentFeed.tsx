'use client'

import { useEffect, useState, useRef } from 'react'

export interface SentimentMessage {
  id: number
  video_id: string
  author: string
  text: string
  score: number
  timestamp: string
}

interface SentimentFeedProps {
  videoId: string | null
  streamTitle?: string
  isLive?: boolean
  onUpdateStats: (score: number) => void
}

function getScoreBadge(score: number) {
  if (score > 0.2) {
    return {
      label: 'Positive',
      textColor: 'text-emerald-400',
      bgColor: 'bg-emerald-500/10',
      borderColor: 'border-emerald-500/20',
      dotColor: 'bg-emerald-400',
    }
  }
  if (score < -0.2) {
    return {
      label: 'Negative',
      textColor: 'text-rose-400',
      bgColor: 'bg-rose-500/10',
      borderColor: 'border-rose-500/20',
      dotColor: 'bg-rose-400',
    }
  }
  return {
    label: 'Neutral',
    textColor: 'text-zinc-400',
    bgColor: 'bg-zinc-800/40',
    borderColor: 'border-zinc-700/30',
    dotColor: 'bg-zinc-400',
  }
}

// Generate deterministic avatar gradient from author name
function getAvatarGradient(name: string) {
  const gradients = [
    'from-indigo-500 to-purple-600',
    'from-blue-500 to-cyan-500',
    'from-emerald-500 to-teal-600',
    'from-rose-500 to-orange-500',
    'from-amber-500 to-yellow-600',
    'from-violet-500 to-pink-500',
  ]
  let hash = 0
  for (let i = 0; i < name.length; i++) {
    hash = name.charCodeAt(i) + ((hash << 5) - hash)
  }
  return gradients[Math.abs(hash) % gradients.length]
}

export function SentimentFeed({
  videoId,
  streamTitle,
  isLive,
  onUpdateStats,
}: SentimentFeedProps) {
  const [messages, setMessages] = useState<SentimentMessage[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const [autoScroll, setAutoScroll] = useState(true)
  const [newCountWhilePaused, setNewCountWhilePaused] = useState(0)

  const wsRef = useRef<WebSocket | null>(null)
  const processedIdsRef = useRef<Set<number>>(new Set())
  const feedContainerRef = useRef<HTMLDivElement>(null)
  const onUpdateStatsRef = useRef(onUpdateStats)

  useEffect(() => {
    onUpdateStatsRef.current = onUpdateStats
  }, [onUpdateStats])

  // Single authoritative lifecycle effect for video selection
  useEffect(() => {
    if (!videoId) {
      setMessages([])
      return
    }

    let isCancelled = false
    setMessages([])
    setIsLoading(true)
    setNewCountWhilePaused(0)
    processedIdsRef.current.clear()

    if (wsRef.current) {
      wsRef.current.close()
      wsRef.current = null
    }

    const initFeed = async () => {
      try {
        const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
        const res = await fetch(`${apiUrl}/v1/analytics/${videoId}`, { cache: 'no-store' })
        
        if (!res.ok || isCancelled) return
        
        const data = await res.json()
        const recent: SentimentMessage[] = Array.isArray(data.recent) ? data.recent : []
        
        // Seed initial historical messages without triggering incremental animation or replay
        setMessages(recent)
        recent.forEach((m) => processedIdsRef.current.add(m.id))
        setIsLoading(false)

        // Find highest existing ID so websocket ONLY streams messages created strictly after this snapshot
        const highestId = recent.reduce((max, m) => Math.max(max, m.id), 0)

        if (isCancelled) return

        const wsBaseUrl = apiUrl.replace(/^http/, 'ws')
        const ws = new WebSocket(`${wsBaseUrl}/live-feed/${videoId}?last_seen_id=${highestId}`)
        wsRef.current = ws

        ws.onmessage = (event) => {
          if (isCancelled) return
          try {
            const msg: SentimentMessage = JSON.parse(event.data)
            if (msg.video_id === videoId) {
              if (processedIdsRef.current.has(msg.id)) {
                return // Deduplicate
              }
              processedIdsRef.current.add(msg.id)

              setMessages((prev) => [msg, ...prev.slice(0, 74)])
              onUpdateStatsRef.current(msg.score)

              if (!autoScroll) {
                setNewCountWhilePaused((c) => c + 1)
              }
            }
          } catch (err) {
            console.error('Failed to parse incoming WebSocket message', err)
          }
        }

        ws.onerror = (err) => {
          console.warn('WebSocket connection warning:', err)
        }
      } catch (err) {
        if (!isCancelled) {
          console.error('Failed to load initial video analytics', err)
          setIsLoading(false)
        }
      }
    }

    initFeed()

    return () => {
      isCancelled = true
      if (wsRef.current) {
        wsRef.current.close()
        wsRef.current = null
      }
    }
  }, [videoId])

  const scrollToTop = () => {
    if (feedContainerRef.current) {
      feedContainerRef.current.scrollTo({ top: 0, behavior: 'smooth' })
      setNewCountWhilePaused(0)
    }
  }

  if (!videoId) {
    return (
      <div className="flex-1 min-h-[520px] flex flex-col items-center justify-center bg-zinc-900/40 border border-zinc-800/80 rounded-2xl p-8 text-center backdrop-blur-md">
        <div className="w-12 h-12 rounded-2xl bg-zinc-800/80 flex items-center justify-center mb-4 text-zinc-400">
          <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M15 10l4.553-2.276A1 1 0 0121 8.618v6.764a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z" />
          </svg>
        </div>
        <h4 className="text-base font-medium text-zinc-300 mb-1">No stream selected</h4>
        <p className="text-sm text-zinc-500 max-w-sm">
          Select a live stream or past broadcast from the left sidebar to inspect live audience vibes.
        </p>
      </div>
    )
  }

  return (
    <div className="flex-1 min-h-[560px] bg-zinc-900/50 border border-zinc-800/80 rounded-2xl p-5 flex flex-col shadow-xl backdrop-blur-md relative overflow-hidden">
      {/* Feed Header */}
      <div className="flex items-center justify-between pb-4 border-b border-zinc-800/80 mb-4 gap-3">
        <div className="flex items-center gap-3 min-w-0">
          <div className="flex items-center gap-2">
            <span className="relative flex h-2.5 w-2.5">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-rose-400 opacity-75"></span>
              <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-rose-500"></span>
            </span>
            <h3 className="text-sm font-semibold text-zinc-200 uppercase tracking-wider">
              Live Stream Chat Vibe
            </h3>
          </div>
          {isLive && (
            <span className="inline-flex items-center px-2 py-0.5 rounded text-[11px] font-semibold bg-rose-500/10 text-rose-400 border border-rose-500/30">
              LIVE CHAT
            </span>
          )}
        </div>

        <div className="flex items-center gap-2">
          {newCountWhilePaused > 0 && (
            <button
              onClick={scrollToTop}
              className="text-xs bg-indigo-600 hover:bg-indigo-500 text-white font-medium px-2.5 py-1 rounded-full shadow-lg transition-all animate-pulse"
            >
              +{newCountWhilePaused} new comments ↑
            </button>
          )}
          <button
            onClick={() => setAutoScroll((v) => !v)}
            className={`text-xs px-2.5 py-1 rounded-lg border transition-colors flex items-center gap-1.5 ${
              autoScroll
                ? 'bg-zinc-800 border-zinc-700 text-zinc-300'
                : 'bg-zinc-900 border-zinc-700/50 text-zinc-500'
            }`}
            title="Toggle automatic pinning to newest comments"
          >
            <span className={`w-1.5 h-1.5 rounded-full ${autoScroll ? 'bg-emerald-400' : 'bg-zinc-500'}`}></span>
            Auto-scroll: {autoScroll ? 'On' : 'Paused'}
          </button>
        </div>
      </div>

      {/* Messages List Container */}
      <div
        ref={feedContainerRef}
        className="flex-1 overflow-y-auto space-y-2.5 pr-2 scrollbar-thin scrollbar-thumb-zinc-700 scrollbar-track-transparent"
      >
        {isLoading && (
          <div className="flex flex-col items-center justify-center h-full text-zinc-500 space-y-3 py-16">
            <div className="w-7 h-7 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin"></div>
            <p className="text-xs text-zinc-400">Connecting to stream feed...</p>
          </div>
        )}

        {!isLoading && messages.length === 0 && (
          <div className="flex flex-col items-center justify-center h-full text-zinc-500 space-y-2 py-16">
            <svg className="w-8 h-8 text-zinc-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
            </svg>
            <p className="text-xs">No comments received yet. Waiting for live chatter...</p>
          </div>
        )}

        {messages.map((msg) => {
          const badge = getScoreBadge(msg.score)
          const avatarGradient = getAvatarGradient(msg.author || 'User')
          const timeFormatted = msg.timestamp
            ? new Date(msg.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
            : ''

          return (
            <div
              key={msg.id}
              className="group p-3 rounded-xl bg-zinc-900/80 border border-zinc-800/80 hover:border-zinc-700 transition-all flex items-start gap-3 shadow-sm"
            >
              {/* User Avatar */}
              <div
                className={`w-7 h-7 rounded-lg bg-gradient-to-br ${avatarGradient} flex items-center justify-center text-white text-xs font-bold shrink-0 mt-0.5 shadow-sm`}
              >
                {(msg.author || 'U').charAt(0).toUpperCase()}
              </div>

              {/* Message Content */}
              <div className="flex-1 min-w-0">
                <div className="flex items-center justify-between gap-2 mb-1">
                  <div className="flex items-center gap-2 min-w-0">
                    <span className="text-xs font-medium text-zinc-300 truncate">
                      {msg.author || 'Anonymous'}
                    </span>
                    <span className="text-[10px] text-zinc-500 shrink-0 font-mono">
                      {timeFormatted}
                    </span>
                  </div>

                  {/* Sentiment Score Pill */}
                  <div
                    className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full border text-[11px] font-mono font-medium ${badge.bgColor} ${badge.textColor} ${badge.borderColor}`}
                  >
                    <span className={`w-1.5 h-1.5 rounded-full ${badge.dotColor}`}></span>
                    <span>{msg.score > 0 ? `+${msg.score.toFixed(2)}` : msg.score.toFixed(2)}</span>
                    <span className="text-[10px] opacity-70 uppercase hidden sm:inline">{badge.label}</span>
                  </div>
                </div>

                <p className="text-sm text-zinc-200 leading-relaxed break-words font-normal">
                  {msg.text}
                </p>
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
