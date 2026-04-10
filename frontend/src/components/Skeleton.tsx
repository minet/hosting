export default function Skeleton({ className = '' }: { className?: string }) {
  return <div className={`animate-pulse rounded-sm bg-neutral-100 dark:bg-neutral-800 ${className}`} />
}

export function CardSkeleton({ className = '' }: { className?: string }) {
  return (
    <div className={`border border-neutral-100 dark:border-neutral-800 shadow-md dark:shadow-none rounded-sm bg-white dark:bg-neutral-900 px-5 py-4 flex flex-col gap-3 ${className}`}>
      <div className="flex items-center gap-2">
        <div className="w-2.5 h-2.5 rounded-full bg-neutral-200 dark:bg-neutral-700 animate-pulse" />
        <div className="h-3 w-24 rounded bg-neutral-200 dark:bg-neutral-700 animate-pulse" />
        <div className="ml-auto h-4 w-14 rounded-full bg-neutral-100 dark:bg-neutral-800 animate-pulse" />
      </div>
      <div className="flex-1 flex flex-col gap-2 justify-center">
        <div className="h-2 w-3/4 rounded bg-neutral-100 dark:bg-neutral-800 animate-pulse" />
        <div className="h-2 w-1/2 rounded bg-neutral-100 dark:bg-neutral-800 animate-pulse" />
        <div className="h-2 w-2/3 rounded bg-neutral-100 dark:bg-neutral-800 animate-pulse" />
      </div>
    </div>
  )
}

export function ChartCardSkeleton({ className = '' }: { className?: string }) {
  return (
    <div className={`border border-neutral-100 dark:border-neutral-800 shadow-md dark:shadow-none rounded-sm bg-white dark:bg-neutral-900 px-4 py-3 flex flex-col ${className}`}>
      <div className="flex items-center gap-2 mb-2">
        <div className="w-2 h-2 rounded-full bg-neutral-200 dark:bg-neutral-700 animate-pulse" />
        <div className="h-3 w-20 rounded bg-neutral-200 dark:bg-neutral-700 animate-pulse" />
        <div className="ml-auto h-4 w-10 rounded-full bg-neutral-100 dark:bg-neutral-800 animate-pulse" />
      </div>
      <div className="flex-1 rounded bg-neutral-50 dark:bg-neutral-800 animate-pulse" />
    </div>
  )
}
