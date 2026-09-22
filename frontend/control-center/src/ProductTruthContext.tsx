import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { readProductTruth } from "./productPayloadRuntimeAdapter";

type ProductTruthContextValue = {
  payload: unknown | null;
  error: string | null;
  refreshing: boolean;
  refreshProductTruth: () => Promise<void>;
};

const ProductTruthContext = createContext<ProductTruthContextValue | null>(null);

export function ProductTruthProvider({ children }: { children: ReactNode }) {
  const [payload, setPayload] = useState<unknown | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const refreshInFlight = useRef<Promise<void> | null>(null);

  const refreshProductTruth = useCallback(() => {
    if (refreshInFlight.current) return refreshInFlight.current;

    const request = (async () => {
      setRefreshing(true);
      try {
        let mailboxSyncWarning: string | null = null;
        try {
          const sync = await window.fetch("/api/v1/product-v1/mailbox-sync", {
            method: "POST",
            headers: { Accept: "application/json" },
          });
          if (!sync.ok) mailboxSyncWarning = `Mailbox sync returned ${sync.status}`;
        } catch (reason: unknown) {
          mailboxSyncWarning = `Mailbox sync unavailable: ${String(reason)}`;
        }

        // Mailbox freshness enriches Product Truth; it is not availability authority.
        // Gmail quota/network failures must not take the Control Center down.
        const truth = await readProductTruth<unknown>({ fresh: true });
        setPayload(truth);
        setError(null);
        if (mailboxSyncWarning) console.warn(mailboxSyncWarning);
      } catch (reason: unknown) {
        setError(String(reason));
        throw reason;
      } finally {
        refreshInFlight.current = null;
        setRefreshing(false);
      }
    })();

    refreshInFlight.current = request;
    return request;
  }, []);

  useEffect(() => {
    let active = true;
    readProductTruth<unknown>()
      .then((truth) => {
        if (!active) return;
        setPayload(truth);
        setError(null);
        void refreshProductTruth().catch(() => undefined);
      })
      .catch((reason: unknown) => {
        if (active) setError(String(reason));
      });

    const interval = window.setInterval(() => {
      void refreshProductTruth().catch(() => undefined);
    }, 30 * 60 * 1000);

    return () => {
      active = false;
      window.clearInterval(interval);
    };
  }, [refreshProductTruth]);

  const value = useMemo<ProductTruthContextValue>(
    () => ({ payload, error, refreshing, refreshProductTruth }),
    [payload, error, refreshing, refreshProductTruth],
  );

  return <ProductTruthContext.Provider value={value}>{children}</ProductTruthContext.Provider>;
}

export function useProductTruth<T>() {
  const context = useContext(ProductTruthContext);
  if (!context) throw new Error("useProductTruth must be used inside ProductTruthProvider");
  return {
    payload: context.payload as T | null,
    error: context.error,
    refreshing: context.refreshing,
    refreshProductTruth: context.refreshProductTruth,
  };
}
