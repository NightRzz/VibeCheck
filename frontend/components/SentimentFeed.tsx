'use client'

import { useEffect, useState, useRef } from 'react'

interface SentimentMessage {
  id: number
  video_id: string
  author: string
  text: string
  score: number
  timestamp: string
}

interface SentimentFeedProps {
  videoId: string | null
  onUpdateStats: (score: number) => void
}

export function SentimentFeed({ videoId, onUpdateStats }: SentimentFeedProps) {
  const [messages, setMessages] = useState<SentimentMessage[]>([])
  const [isWaiting, setIsWaiting] = useState(false)
  const wsRef = useRef<WebSocket | null>(null)
  const onUpdateStatsRef = useRef(onUpdateStats)

  const feedContainerRef = useRef<HTMLDivElement>(null)
  const processedIdsRef = useRef<Set<number>>(new Set())

  // Track whether the user is near the top so newest-first inserts can stay visible.
  const isScrolledToTop = useRef(true)

  const handleScroll = () => {
    if (!feedContainerRef.current) return
    const { scrollTop } = feedContainerRef.current
    isScrolledToTop.current = scrollTop < 50
  }

  // Keep the latest stats callback without forcing websocket reconnects.
  useEffect(() => {
    onUpdateStatsRef.current = onUpdateStats
  }, [onUpdateStats])

  useEffect(() => {
    if (!videoId) return

    setMessages([])
    setIsWaiting(true)
    processedIdsRef.current.clear()

    const fetchRecent = async () => {
      try {
        const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
        const res = await fetch(`${apiUrl}/v1/analytics/${videoId}`)
        if (res.ok) {
           const data = await res.json()
           if (data.recent && Array.isArray(data.recent)) {
              const recentMsgs = data.recent
              setMessages(recentMsgs)
              recentMsgs.forEach((m: SentimentMessage) => processedIdsRef.current.add(m.id))
              if (recentMsgs.length > 0) {
                 setIsWaiting(false)
              }
              // Do NOT scroll down on initial fetch anymore!
           }
        }
      } catch (err) {
        console.error('Failed to fetch recent messages', err)
      }
    }
    
    fetchRecent()

    const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
    const wsUrl = apiUrl.replace(/^http/, 'ws') + `/live-feed/${videoId}`

    const ws = new WebSocket(wsUrl)
    wsRef.current = ws

    ws.onmessage = (event) => {
      try {
        const msg: SentimentMessage = JSON.parse(event.data)
        if (msg.video_id === videoId) {
          setIsWaiting(false)
          
          if (processedIdsRef.current.has(msg.id)) {
            return
          }
          
          processedIdsRef.current.add(msg.id)
          
          setMessages((prev) => {
            return [msg, ...prev.slice(0, 49)]
          })
          
          onUpdateStatsRef.current(msg.score)

          // Keep viewport pinned to newest messages only when user is already near top.
          setTimeout(() => {
            if (feedContainerRef.current && isScrolledToTop.current) {
              feedContainerRef.current.scrollTo({
                top: 0,
                behavior: 'smooth'
              });
            }
          }, 50)
        }
      } catch (err) {
        console.error('Failed to parse WS message', err)
      }
    }

    return () => {
      ws.close()
    }
  }, [videoId])

  if (!videoId) {
    return (
      <div className="flex-1 flex items-center justify-center bg-gray-900 border border-gray-700 rounded-lg p-8">
        <p className="text-gray-500">Select a stream to view sentiment</p>
      </div>
    )
  }

  return (
    <div className="flex-1 bg-gray-900 border border-gray-700 rounded-lg p-4 flex flex-col h-[500px]">
      <h3 className="text-lg font-semibold mb-4 text-white border-b border-gray-700 pb-2">
        Live Sentiment Feed
      </h3>
      <div 
        ref={feedContainerRef} 
        onScroll={handleScroll}
        className="flex-1 overflow-y-auto pr-2 space-y-3 scrollbar-thin scrollbar-thumb-gray-600"
      >
        {messages.length === 0 && isWaiting && (
            <div className="flex flex-col items-center justify-center h-full text-gray-500 space-y-4">
                <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500"></div>
                <p>Waiting for new comments to parse...</p>
            </div>
        )}
        {messages.length === 0 && !isWaiting && (
            <div className="flex items-center justify-center h-full text-gray-500">
                <p>No messages yet.</p>
            </div>
        )}
        {messages.map((msg, idx) => (
          <div
            key={msg.id || idx}
            className={`p-3 rounded-lg border-l-4 ${
              msg.score > 0.2
                ? 'bg-green-900/20 border-green-500'
                : msg.score < -0.2
                ? 'bg-red-900/20 border-red-500'
                : 'bg-gray-800 border-gray-500'
            }`}
          >
            <div className="flex justify-between items-start mb-1">
              <span className="text-sm text-gray-400">
                <span className="font-semibold text-gray-300 mr-2">{msg.author}</span>
                {new Date(msg.timestamp).toLocaleString()}
              </span>
              <span
                className={`text-xs font-bold px-2 py-1 rounded-full ${
                  msg.score > 0.2
                    ? 'text-green-400 bg-green-900/50'
                    : msg.score < -0.2
                    ? 'text-red-400 bg-red-900/50'
                    : 'text-gray-300 bg-gray-700'
                }`}
              >
                {msg.score.toFixed(2)}
              </span>
            </div>
            <p className="text-white text-sm break-words">{msg.text}</p>
          </div>
        ))}
      </div>
    </div>
  )
}
