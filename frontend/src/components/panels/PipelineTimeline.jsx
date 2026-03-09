import { PIPELINE_PHASES } from '../../utils/formatters'

export default function PipelineTimeline({ log }) {
  const reached = new Set()
  log.forEach(l => {
    const phase = (l.phase || '').toLowerCase()
    if (phase.includes('ingestion')) reached.add('ingestion')
    if (phase.includes('research') || phase === 'research_complete') {
      reached.add('ingestion')
      reached.add('research')
    }
    if (phase.includes('reasoning')) {
      reached.add('ingestion')
      reached.add('research')
      reached.add('reasoning')
    }
    if (phase === 'done') PIPELINE_PHASES.forEach(p => reached.add(p.key))
  })

  return (
    <div className="flex items-start gap-0 mb-4">
      {PIPELINE_PHASES.map((p, i) => (
        <div key={p.key} className="flex items-center">
          <div className="flex flex-col items-center w-20">
            <div className={`w-7 h-7 rounded-full flex items-center justify-center text-[11px] font-bold border-2
              ${reached.has(p.key)
                ? 'bg-brand border-brand text-white'
                : 'bg-white border-slate-300 text-slate-400'}`}>
              {reached.has(p.key) ? '✓' : i + 1}
            </div>
            <span className={`text-[11px] mt-1 text-center leading-tight ${reached.has(p.key) ? 'text-brand font-medium' : 'text-slate-400'}`}>
              {p.label}
            </span>
          </div>
          {i < PIPELINE_PHASES.length - 1 && (
            <div className={`h-0.5 w-6 mb-4 mx-0.5 ${reached.has(PIPELINE_PHASES[i + 1].key) ? 'bg-brand' : 'bg-slate-200'}`} />
          )}
        </div>
      ))}
    </div>
  )
}
