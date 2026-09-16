"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { listAyushProducts } from "@/lib/api";
import type { AyushProduct } from "@/lib/types";

/**
 * The single shared AyushWellness Product Library loading path — the
 * Sidebar's category tree and the Content Pipeline's "AyushWellness Product"
 * dropdown both consume this instead of maintaining their own independent
 * fetch/state, so they can never drift into inconsistent behavior again.
 *
 * `GET /product-library/products` already excludes archived products by
 * default (server-side) — this hook never re-filters by status itself, it
 * just surfaces exactly what the backend considers the active catalog.
 *
 * Error handling is deliberately never `catch(() => setProducts([]))` — an
 * empty array is indistinguishable from "genuinely zero products" once
 * rendered, so a transient failure (e.g. the dev backend mid-restart) would
 * otherwise look identical to an empty catalog with no way to recover short
 * of a full remount. Instead: a distinct `failed` flag, one silent automatic
 * retry for the common transient-blip case, a manual `refresh()` for
 * anything after that, and the last known-good list is never discarded by a
 * later failed background refresh.
 */
export function useAyushProducts(options?: { enabled?: boolean; refreshKey?: unknown }) {
  const enabled = options?.enabled ?? true;
  const refreshKey = options?.refreshKey;

  const [products, setProducts] = useState<AyushProduct[] | null>(null);
  const [failed, setFailed] = useState(false);
  const [retryTick, setRetryTick] = useState(0);
  // Caps the automatic retry to once per failure streak — smooths over a
  // one-off blip without ever hammering a genuinely-down backend.
  const autoRetriedRef = useRef(false);

  useEffect(() => {
    if (!enabled) return;
    let cancelled = false;
    listAyushProducts()
      .then((result) => {
        if (cancelled) return;
        setProducts(result);
        setFailed(false);
        autoRetriedRef.current = false;
      })
      .catch(() => {
        if (cancelled) return;
        setFailed(true);
        if (!autoRetriedRef.current) {
          autoRetriedRef.current = true;
          setTimeout(() => {
            if (!cancelled) setRetryTick((t) => t + 1);
          }, 1500);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [enabled, refreshKey, retryTick]);

  const refresh = useCallback(() => {
    autoRetriedRef.current = false;
    setRetryTick((t) => t + 1);
  }, []);

  return { products, failed, refresh };
}
