// hooks/useDashboardData.ts
import useSWR from 'swr';

const fetcher = (url: string) => fetch(url).then(res => res.json());

export function useDashboardData(userId: string) {
  const { data, error, mutate } = useSWR(
    userId ? `${process.env.NEXT_PUBLIC_API_BASE_URL}/dashboard/user?user_id=${userId}` : null,
    fetcher,
    {
      revalidateOnFocus: false, // ou true, conforme sua necessidade
      dedupingInterval: 60000,  // 1 minuto – evita requisições repetidas
    }
  );

  return {
    dashboardData: data,
    isLoading: !error && !data,
    isError: error,
    mutate, // Para forçar a atualização manualmente, se necessário
  };
}
