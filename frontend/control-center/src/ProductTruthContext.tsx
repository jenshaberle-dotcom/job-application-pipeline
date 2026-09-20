import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
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

  useEffect(() => {
    let active = true;
    readProductTruth<unknown>()
      .then((truth) => {
        if (!active) return;
        setPayload(truth);
        setError(null);
      })
      .catch((reason: unknown) => {
        if (active) setError(String(reason));
      });
    return () => {
      active = false;
    };
  }, []);

  const refreshProductTruth = useCallback(async () => {
    setRefreshing(true);
    try {
      const truth = await readProductTruth<unknown>({ fresh: true });
      setPayload(truth);
      setError(null);
    } catch (reason: unknown) {
      setError(String(reason));
      throw reason;
    } finally {
      setRefreshing(false);
    }
  }, []);

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
