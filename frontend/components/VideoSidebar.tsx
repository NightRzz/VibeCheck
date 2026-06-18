'use client'

interface TrackedVideo {
  id: number
  video_id: string
  title: string
  is_active: boolean
  is_live?: boolean
  live_chat_id?: string | null
  message_count?: number
}

interface VideoSidebarProps {
  videos: TrackedVideo[]
  selectedId: string | null
  onSelect: (videoId: string) => void
  onDelete: (videoId: string) => Promise<void>
}

export function VideoSidebar({
  videos,
  selectedId,
  onSelect,
  onDelete,
}: VideoSidebarProps) {
  return (
    <div className="p-4 flex flex-col h-full">
      <div className="flex items-center justify-between mb-3 px-1">
        <h3 className="text-xs font-semibold text-zinc-400 uppercase tracking-wider flex items-center gap-2">
          <span>Active Channels</span>
          <span className="text-[10px] bg-zinc-800 text-zinc-400 px-1.5 py-0.5 rounded-full font-mono">
            {videos.length}
          </span>
        </h3>
      </div>

      <div className="flex-1 overflow-y-auto space-y-1.5 scrollbar-thin scrollbar-thumb-zinc-700">
        {videos.map((v) => {
          const isSelected = selectedId === v.video_id
          const isLive = Boolean(v.is_live || v.live_chat_id)

          return (
            <div
              key={v.id}
              onClick={() => onSelect(v.video_id)}
              className={`group relative p-3 rounded-xl border transition-all cursor-pointer flex flex-col gap-1.5 ${
                isSelected
                  ? 'bg-zinc-800/90 border-indigo-500/50 shadow-md shadow-indigo-950/20'
                  : 'bg-zinc-900/40 border-zinc-800/60 hover:bg-zinc-800/40 hover:border-zinc-700/80 text-zinc-400'
              }`}
            >
              {/* Header: Title & Badges */}
              <div className="flex items-start justify-between gap-2">
                <div className="min-w-0 flex-1">
                  <h4 className={`text-xs font-semibold truncate ${isSelected ? 'text-white' : 'text-zinc-300'}`}>
                    {v.title || v.video_id}
                  </h4>
                  <div className="text-[10px] font-mono text-zinc-500 mt-0.5 flex items-center gap-1.5">
                    <span>ID: {v.video_id}</span>
                  </div>
                </div>

                {/* Live Pill */}
                {isLive ? (
                  <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-bold bg-rose-500/10 text-rose-400 border border-rose-500/30 shrink-0">
                    <span className="w-1.5 h-1.5 rounded-full bg-rose-500 animate-pulse"></span>
                    LIVE
                  </span>
                ) : (
                  <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium bg-zinc-800 text-zinc-400 border border-zinc-700/50 shrink-0">
                    ARCHIVE
                  </span>
                )}
              </div>

              {/* Action Buttons */}
              <div className="flex items-center justify-between mt-1 pt-1.5 border-t border-zinc-800/40">
                <span className="text-[10px] text-zinc-500 font-mono">
                  {v.message_count !== undefined ? `${v.message_count.toLocaleString()} msgs` : 'Tracking'}
                </span>

                <button
                  onClick={async (e) => {
                    e.stopPropagation()
                    if (confirm(`Stop tracking stream "${v.title || v.video_id}"?`)) {
                      await onDelete(v.video_id)
                    }
                  }}
                  className="opacity-0 group-hover:opacity-100 focus:opacity-100 transition-opacity p-1 text-zinc-500 hover:text-rose-400 rounded hover:bg-rose-500/10"
                  title="Remove stream"
                >
                  <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                  </svg>
                </button>
              </div>
            </div>
          )
        })}

        {videos.length === 0 && (
          <div className="p-6 text-center text-zinc-500 text-xs italic">
            No streams tracked yet. Add one above to begin live inference.
          </div>
        )}
      </div>
    </div>
  )
}
