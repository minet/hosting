import GaugeComponent from 'react-gauge-component'

interface Props {
  label: string
  used: number
  total: number
  unit: string
  color?: string
}

const COLORS: Record<string, string> = {
  blue:    '#3b82f6',
  emerald: '#10b981',
  violet:  '#8b5cf6',
}

export default function ResourceGauge({ label, used, total, unit, color = 'blue' }: Props) {
  const pct = total > 0 ? Math.round((used / total) * 100) : 0
  const fill = COLORS[color] ?? COLORS.blue

  return (
    <div className="flex flex-col items-center justify-center h-full w-full">

      {/* Mobile : compact */}
      <div className="flex md:hidden flex-col items-center justify-center h-full w-full">
        <GaugeComponent
          value={used}
          minValue={0}
          maxValue={total || 1}
          type="semicircle"
          fadeInAnimation={false}

          arc={{
            width: 0.35,
            padding: 0.01,
            cornerRadius: 3,
            subArcs: [
              { limit: used, color: fill, showTick: false },
              { limit: total || 1, color: '#e2e8f0', showTick: false },
            ],
          }}
          pointer={{ hide: true }}
          labels={{
            valueLabel: {
              formatTextValue: () => `${pct}%`,
              style: { fontSize: '26px', fill: '#1e293b', fontWeight: '700', textShadow: 'none' },
            },
            tickLabels: { hideMinMax: true },
          }}
          style={{ width: '100%' }}
        />
        <p className="text-xs font-semibold text-neutral-700 -mt-4">{label}</p>
      </div>

      {/* Tablette */}
      <div className="hidden md:flex xl:hidden flex-col w-full h-full justify-between py-2 px-1">
        <div className="flex items-center gap-1.5 px-1">
          <p className="text-xs font-bold text-neutral-700">{label}</p>
        </div>
        <div className="flex-1 min-h-0 flex items-center overflow-hidden">
          <GaugeComponent
            value={used}
            minValue={0}
            maxValue={total || 1}
            type="semicircle"
            fadeInAnimation={false}
  
            arc={{
              width: 0.38,
              padding: 0.01,
              cornerRadius: 3,
              subArcs: [
                { limit: used, color: fill, showTick: false },
                { limit: total || 1, color: '#e2e8f0', showTick: false },
              ],
            }}
            pointer={{ hide: true }}
            labels={{
              valueLabel: {
                formatTextValue: () => `${pct}%`,
                style: { fontSize: '36px', fill: '#1e293b', fontWeight: '700', textShadow: 'none' },
              },
              tickLabels: { hideMinMax: true },
            }}
            style={{ width: '100%' }}
          />
        </div>
      </div>

      {/* Desktop */}
      <div className="hidden xl:flex flex-col w-full h-full justify-between py-2 px-1">
        <div className="flex items-center gap-1.5 px-1">
          <p className="text-sm font-bold text-neutral-700">{label}</p>
          <span className="text-xs text-neutral-400">({used} / {total} {unit})</span>
        </div>
        <div className="flex-1 min-h-0 flex items-center overflow-hidden">
          <div className="relative w-full">
            <GaugeComponent
              value={used}
              minValue={0}
              maxValue={total || 1}
              type="radial"
              fadeInAnimation={false}
    
              arc={{
                width: 0.2,
                padding: 0.01,
                cornerRadius: 3,
                subArcs: [
                  { limit: used, color: fill, showTick: false },
                  { limit: total || 1, color: '#e2e8f0', showTick: false },
                ],
              }}
              pointer={{ hide: true }}
              labels={{
                valueLabel: {
                  formatTextValue: () => `${pct}%`,
                  style: { fontSize: '36px', fill: '#1e293b', fontWeight: '700', textShadow: 'none' },
                },
                tickLabels: {
                  type: 'outer' as const,
                  ticks: [{ value: 0 }, { value: total }],
                  defaultTickValueConfig: {
                    formatTextValue: (v: number) => `${v}`,
                    style: { fontSize: '11px', fill: '#94a3b8', textShadow: 'none' },
                  },
                },
              }}
              style={{ width: '100%' }}
            />
          </div>
        </div>
      </div>

    </div>
  )
}
