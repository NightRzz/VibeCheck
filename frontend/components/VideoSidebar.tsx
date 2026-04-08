'use client'

interface TrackedVideo {
  id: number
  video_id: string
  title: string
  is_active: boolean
}

interface VideoSidebarProps {
  videos: TrackedVideo[]
  onSelect: (videoId: string) => void
  selectedId: string | null
  onDelete: (videoId: string) => Promise<void>
}

export function VideoSidebar({
  videos,
  onSelect,
  selectedId,
  onDelete,
}: VideoSidebarProps) {
  return (
    <div className="w-full md:w-64 bg-gray-800 p-4 border-r border-gray-700 h-full overflow-y-auto">
      <h2 className="text-xl font-bold mb-4 text-white flex items-center gap-2">
        <i className="icon-youtube text-red-500"></i> Tracked Streams
      </h2>
      <ul className="space-y-2">
        {videos.map((v) => (
          <li key={v.id} className="relative group">
            <button
              onClick={() => onSelect(v.video_id)}
              className={`w-full text-left px-3 py-2 pr-10 rounded-md transition-colors ${
                selectedId === v.video_id
                  ? 'bg-blue-600 text-white'
                  : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
              }`}
            >
              <div className="flex items-center justify-between">
                <span className="truncate flex-1 font-medium text-sm">
                  {v.title || v.video_id}
                </span>
                {v.is_active && (
                  <span className="flex h-2 w-2 relative ml-2 shrink-0">
                    <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-red-400 opacity-75"></span>
                    <span className="relative inline-flex rounded-full h-2 w-2 bg-red-500"></span>
                  </span>
                )}
              </div>
            </button>
            <button
              onClick={async (e: any) => {
                e.stopPropagation();
                await onDelete(v.video_id);
              }}
              className="absolute right-2 top-1/2 -translate-y-1/2 p-1 text-gray-400 hover:text-red-500 opacity-0 group-hover:opacity-100 transition-opacity focus:opacity-100"
              title="Delete stream"
            >
              <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
              </svg>
            </button>
          </li>
        ))}
        {videos.length === 0 && (
          <li className="text-gray-500 text-sm italic p-2">
            No active streams
          </li>
        )}
      </ul>
    </div>
  )
}
