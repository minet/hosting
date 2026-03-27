import { useMutation, useQueryClient, type UseMutationResult } from '@tanstack/react-query'
import { useToast } from '../contexts/ToastContext'

interface Options<TArgs, TResult> {
  mutationFn: (args: TArgs) => Promise<TResult>
  /** Query keys to invalidate on success */
  invalidate?: string[][]
  /** Success message shown as toast (omit for no toast) */
  successMessage?: string
  /** Fallback error message if the error has no .message */
  fallbackError?: string
  /** Callback after successful mutation */
  onSuccess?: (data: TResult, args: TArgs) => void
}

/**
 * Thin wrapper around useMutation that standardises error toasting
 * and query invalidation across the app.
 */
export function useMutationWithToast<TArgs = void, TResult = unknown>(
  opts: Options<TArgs, TResult>,
): UseMutationResult<TResult, Error, TArgs> {
  const { toast } = useToast()
  const qc = useQueryClient()

  return useMutation({
    mutationFn: opts.mutationFn,
    onSuccess: (data, args) => {
      if (opts.invalidate) {
        for (const key of opts.invalidate) {
          qc.invalidateQueries({ queryKey: key })
        }
      }
      if (opts.successMessage) toast(opts.successMessage)
      opts.onSuccess?.(data, args)
    },
    onError: (err) => {
      const msg = err instanceof Error ? err.message : (opts.fallbackError ?? 'Une erreur est survenue')
      toast(msg)
    },
  })
}
