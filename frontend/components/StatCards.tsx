'use client'

interface StatCardsProps {
  totalMsgs: number
  avgScore: number
  minScore: number
  maxScore: number
}

export function StatCards({
  totalMsgs,
  avgScore,
  minScore,
  maxScore,
}: StatCardsProps) {
  const isPositive = avgScore > 0.15
  const isNegative = avgScore < -0.15

  const sentimentLabel = isPositive
    ? 'Positive Vibe'
    : isNegative
    ? 'Negative Vibe'
    : 'Neutral Vibe'

  const sentimentColor = isPositive
    ? 'text-emerald-400'
    : isNegative
    ? 'text-rose-400'
    : 'text-amber-400'

  const sentimentBg = isPositive
    ? 'bg-emerald-500/10 border-emerald-500/20'
    : isNegative
    ? 'bg-rose-500/10 border-rose-500/20'
    : 'bg-amber-500/10 border-amber-500/20'

  // Calculate sentiment distribution percentage for a gauge bar
  const normalizedScore = (avgScore + 1) / 2 // 0.0 to 1.0
  const gaugePercent = Math.max(0, Math.min(100, Math.round(normalizedScore * 100)))

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
      {/* 1. Primary Sentiment Metric */}
      <div className="bg-zinc-900/60 border border-zinc-800/80 rounded-2xl p-4 shadow-lg backdrop-blur-md flex flex-col justify-between">
        <div className="flex items-center justify-between mb-2">
          <span className="text-xs font-semibold uppercase tracking-wider text-zinc-400">Audience Sentiment</span>
          <span className={`text-[11px] font-semibold px-2 py-0.5 rounded-full border ${sentimentBg} ${sentimentColor}`}>
            {sentimentLabel}
          </span>
        </div>
        <div className="flex items-baseline gap-2 mb-3">
          <span className={`text-3xl font-extrabold tracking-tight font-mono ${sentimentColor}`}>
            {avgScore > 0 ? `+${avgScore.toFixed(2)}` : avgScore.toFixed(2)}
          </span>
          <span className="text-xs text-zinc-500 font-mono">/ scale [-1, +1]</span>
        </div>
        {/* Progress Gauge Bar */}
        <div className="w-full bg-zinc-800 h-1.5 rounded-full overflow-hidden flex">
          <div
            className={`h-full transition-all duration-500 ${isPositive ? 'bg-emerald-500' : isNegative ? 'bg-rose-500' : 'bg-amber-500'}`}
            style={{ width: `${gaugePercent}%` }}
          ></div>
        </div>
      </div>

      {/* 2. Total Messages */}
      <div className="bg-zinc-900/60 border border-zinc-800/80 rounded-2xl p-4 shadow-lg backdrop-blur-md flex flex-col justify-between">
        <div className="flex items-center justify-between mb-2">
          <span className="text-xs font-semibold uppercase tracking-wider text-zinc-400">Volume Streamed</span>
          <span className="w-2 h-2 rounded-full bg-indigo-400 animate-ping"></span>
        </div>
        <div className="flex items-baseline gap-2 mb-2">
          <span className="text-3xl font-extrabold tracking-tight font-mono text-zinc-100">
            {totalMsgs.toLocaleString()}
          </span>
          <span className="text-xs text-zinc-500">comments</span>
        </div>
        <div className="text-[11px] text-zinc-500 flex items-center gap-1.5">
          <span className="w-1.5 h-1.5 rounded-full bg-emerald-400"></span>
          <span>Kafka ingestion active</span>
        </div>
      </div>

      {/* 3. Sentiment Range & Extremes */}
      <div className="bg-zinc-900/60 border border-zinc-800/80 rounded-2xl p-4 shadow-lg backdrop-blur-md flex flex-col justify-between">
        <div className="flex items-center justify-between mb-2">
          <span className="text-xs font-semibold uppercase tracking-wider text-zinc-400">Sentiment Range</span>
          <span className="text-[11px] font-mono text-zinc-400 bg-zinc-800/80 px-1.5 py-0.5 rounded">
            ± Extremes
          </span>
        </div>
        <div className="flex items-center justify-between font-mono text-sm mb-3">
          <div className="flex flex-col">
            <span className="text-[10px] text-zinc-500 uppercase">Min Score</span>
            <span className="text-rose-400 font-bold">{minScore.toFixed(2)}</span>
          </div>
          <div className="h-6 w-px bg-zinc-800"></div>
          <div className="flex flex-col text-right">
            <span className="text-[10px] text-zinc-500 uppercase">Max Score</span>
            <span className="text-emerald-400 font-bold">{maxScore > 0 ? `+${maxScore.toFixed(2)}` : maxScore.toFixed(2)}</span>
          </div>
        </div>
        <div className="text-[11px] text-zinc-500">Polarity range across broadcast</div>
      </div>

      {/* 4. AI Engine Health */}
      <div className="bg-zinc-900/60 border border-zinc-800/80 rounded-2xl p-4 shadow-lg backdrop-blur-md flex flex-col justify-between">
        <div className="flex items-center justify-between mb-2">
          <span className="text-xs font-semibold uppercase tracking-wider text-zinc-400">Model Pipeline</span>
          <span className="text-[11px] text-purple-400 bg-purple-500/10 border border-purple-500/20 px-2 py-0.5 rounded-full font-semibold">
            ONNX INT8
          </span>
        </div>
        <div className="mb-2">
          <div className="text-sm font-semibold text-zinc-200 truncate">Twitter-RoBERTa</div>
          <div className="text-xs text-zinc-500">Contextual Self-Attention</div>
        </div>
        <div className="flex items-center justify-between text-[11px] text-zinc-400 font-mono">
          <span>Inference: ~8ms</span>
          <span className="text-emerald-400">LRU: 0.001ms</span>
        </div>
      </div>
    </div>
  )
}
