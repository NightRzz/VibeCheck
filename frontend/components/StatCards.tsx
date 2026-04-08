'use client'

export function StatCards({
  totalMsgs,
  avgScore,
  range,
}: {
  totalMsgs: number
  avgScore: number
  range: string
}) {
  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
      <div className="bg-gray-800 p-4 rounded-lg shadow-md flex items-center justify-between border border-gray-700">
        <div>
          <p className="text-sm text-gray-400 font-semibold mb-1">Total Messages</p>
          <p className="text-2xl font-bold text-white">{totalMsgs}</p>
        </div>
        <div className="text-blue-500 text-3xl">
          <i className="icon-pulse"></i>
        </div>
      </div>
      
      <div className="bg-gray-800 p-4 rounded-lg shadow-md flex items-center justify-between border border-gray-700">
        <div>
          <p className="text-sm text-gray-400 font-semibold mb-1">Average Vibe</p>
          <p className="text-2xl font-bold text-white">{avgScore.toFixed(2)}</p>
        </div>
        <div className="text-green-500 text-3xl">
           <i className="icon-gauge"></i>
        </div>
      </div>
      
      <div className="bg-gray-800 p-4 rounded-lg shadow-md flex items-center justify-between border border-gray-700">
        <div>
          <p className="text-sm text-gray-400 font-semibold mb-1">Vibe Range</p>
          <p className="text-2xl font-bold text-white">{range}</p>
        </div>
        <div className="text-purple-500 text-3xl">
          <span className="font-mono text-xl">±</span>
        </div>
      </div>
    </div>
  )
}
