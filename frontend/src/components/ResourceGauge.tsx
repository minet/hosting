import GaugeComponent from 'react-gauge-component'
import { useMediaQuery } from '../hooks/useMediaQuery'
import { useTheme } from '../contexts/ThemeContext'

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
  const isXl = useMediaQuery('(min-width: 1280px)')
  const isMd = useMediaQuery('(min-width: 768px)')
  const { theme } = useTheme()
  const isDark = theme === 'dark'

  const trackColor = isDark ? '#334155' : '#e2e8f0'
  const textColor = isDark ? '#e2e8f0' : '#1e293b'
  const mutedColor = isDark ? '#64748b' : '#94a3b8'
  const labelColor = isDark ? '#d4d4d8' : undefined

  // Mobile: compact semicircle
  if (!isMd) {
    return (
      <div className="flex flex-col items-center justify-center h-full w-full">
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
              { limit: total || 1, color: trackColor, showTick: false },
            ],
          }}
          pointer={{ hide: true }}
          labels={{
            valueLabel: {
              formatTextValue: () => `${pct}%`,
              style: { fontSize: '26px', fill: textColor, fontWeight: '700', textShadow: 'none' },
            },
            tickLabels: { hideMinMax: true },
          }}
          style={{ width: '100%' }}
        />
        <p className="text-xs font-semibold text-neutral-700 dark:text-neutral-300 -mt-4">{label}</p>
      </div>
    )
  }

  // Desktop (xl+): radial with tick labels
  if (isXl) {
    return (
      <div className="flex flex-col w-full h-full justify-between py-2 px-1">
        <div className="flex items-center gap-1.5 px-1">
          <p className="text-sm font-bold text-neutral-700 dark:text-neutral-300">{label}</p>
          <span className="text-xs text-neutral-400 dark:text-neutral-500">({used} / {total} {unit})</span>
        </div>
        <div className="flex-1 min-h-0 relative">
          <div className="absolute inset-0 flex items-center justify-center overflow-hidden">
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
                  { limit: total || 1, color: trackColor, showTick: false },
                ],
              }}
              pointer={{ hide: true }}
              labels={{
                valueLabel: {
                  formatTextValue: () => `${pct}%`,
                  style: { fontSize: '36px', fill: textColor, fontWeight: '700', textShadow: 'none' },
                },
                tickLabels: {
                  type: 'outer' as const,
                  ticks: [{ value: 0 }, { value: total }],
                  defaultTickValueConfig: {
                    formatTextValue: (v: number) => `${v}`,
                    style: { fontSize: '11px', fill: mutedColor, textShadow: 'none' },
                  },
                },
              }}
              style={{ width: '100%' }}
            />
          </div>
        </div>
      </div>
    )
  }

  // Tablet (md to xl): semicircle with label
  return (
    <div className="flex flex-col w-full h-full justify-between py-2 px-1">
      <div className="flex items-center gap-1.5 px-1">
        <p className="text-xs font-bold text-neutral-700 dark:text-neutral-300">{label}</p>
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
              { limit: total || 1, color: trackColor, showTick: false },
            ],
          }}
          pointer={{ hide: true }}
          labels={{
            valueLabel: {
              formatTextValue: () => `${pct}%`,
              style: { fontSize: '36px', fill: textColor, fontWeight: '700', textShadow: 'none' },
            },
            tickLabels: { hideMinMax: true },
          }}
          style={{ width: '100%' }}
        />
      </div>
    </div>
  )
}
