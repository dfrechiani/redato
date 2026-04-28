import { useState, useEffect } from "react";

export function useSSE<T>(userId: string | null, activeRequestId?: string | null) {
  const [sseData, setSseData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!userId) return;
    let evtSource: EventSource | null = null;
    let reconnectTimeout: NodeJS.Timeout | null = null;

    const connect = () => {
      const sseUrl = `${process.env.NEXT_PUBLIC_API_BASE_URL}/sse/${userId}`;
      evtSource = new EventSource(sseUrl);

      evtSource.onopen = () => {
        console.info("SSE connection established");
        setError(null);
      };

      evtSource.onmessage = (event) => {
        try {
          const parsedData: T = JSON.parse(event.data);
          console.log("SSE message received:", parsedData);

          // Filtra eventos para garantir que pertencem à request atual
          if (activeRequestId && (parsedData as any).request_id !== activeRequestId) {
            console.log("Ignoring event for a different request_id:", (parsedData as any).request_id);
            return;
          }

          setSseData(parsedData);
        } catch (err) {
          console.error("Error parsing SSE data:", err);
        }
      };

      evtSource.onerror = (err) => {
        console.error("SSE encountered error:", err);
        setError("SSE connection error, attempting to reconnect...");
        evtSource?.close();

        reconnectTimeout = setTimeout(connect, 3000);
      };
    };

    connect();

    return () => {
      evtSource?.close();
      if (reconnectTimeout) clearTimeout(reconnectTimeout);
    };
  }, [userId, activeRequestId]);

  return { sseData, error };
}
