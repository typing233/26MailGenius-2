import { useQuery } from '@tanstack/react-query';

export function usePolling<T>(
  queryKey: string[],
  queryFn: () => Promise<T>,
  intervalMs: number,
  enabled: boolean = true
) {
  return useQuery({
    queryKey,
    queryFn,
    refetchInterval: enabled ? intervalMs : false,
    enabled,
  });
}
