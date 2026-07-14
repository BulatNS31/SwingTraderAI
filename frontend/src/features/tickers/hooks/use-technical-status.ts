import { tickerApi } from '../api/ticker-api'
import { useQuery } from '@tanstack/react-query';


export function useTechnicalStatus(symbol: string) {
    return useQuery({
        queryKey: ['technical-status', symbol],
        queryFn: () => tickerApi.getTechnicalStatus(symbol),
        enabled: !!symbol,
        staleTime: 60_000,
    })
}
