import type { DirectSpectrumPayload, ViewState } from "../api/bridge";

export const FOLLOW_TRIGGER_RATIO = 0.78;
export const FOLLOW_TARGET_RATIO = 0.24;
export const FOLLOW_PAGE_RATIO = FOLLOW_TRIGGER_RATIO - FOLLOW_TARGET_RATIO;

export function spectrumLayersForMode(mode: "raw" | "tracks" | "both") {
  return { raw: mode !== "tracks", tracks: mode !== "raw" };
}

export type SpectrumRegion = {
  startTime: number;
  endTime: number;
  minMidi: number;
  maxMidi: number;
  pixelWidth: number;
  pixelHeight: number;
  threshold: number;
};

export function followViewportStart(
  viewStart: number,
  windowSeconds: number,
  playbackTime: number,
  duration: number,
): number | null {
  if (windowSeconds <= 0) return null;
  const trigger = viewStart + windowSeconds * FOLLOW_TRIGGER_RATIO;
  if (playbackTime >= viewStart && playbackTime <= trigger) return null;

  const maxStart = Math.max(0, duration - windowSeconds);
  let next: number;
  if (playbackTime > trigger && playbackTime <= viewStart + windowSeconds) {
    // Normal page-follow. Keeping this start exact lets the prefetched page be reused.
    next = viewStart + windowSeconds * FOLLOW_PAGE_RATIO;
  } else {
    // A seek/jump outside the current viewport lands directly in the target zone.
    next = playbackTime - windowSeconds * FOLLOW_TARGET_RATIO;
  }
  next = Math.max(0, Math.min(maxStart, next));
  return Math.abs(next - viewStart) > 1e-6 ? next : null;
}

export function nextPrefetchStart(viewStart: number, windowSeconds: number, duration: number): number | null {
  if (windowSeconds <= 0) return null;
  const next = Math.min(Math.max(0, duration - windowSeconds), viewStart + windowSeconds * FOLLOW_PAGE_RATIO);
  return next > viewStart + 1e-6 ? next : null;
}

export function spectrumRegion(
  view: ViewState,
  viewport: { width: number; height: number },
  threshold: number,
  startTime = view.start,
): SpectrumRegion {
  return {
    startTime,
    endTime: startTime + view.windowSeconds,
    minMidi: view.pitchBottom - 0.5,
    maxMidi: view.pitchBottom + view.visibleNotes - 0.5,
    pixelWidth: Math.max(1, Math.round(viewport.width)),
    pixelHeight: Math.max(1, Math.round(viewport.height)),
    threshold,
  };
}

function stableNumber(value: number): number {
  return Math.round(value * 1e6) / 1e6;
}

export function spectrumRegionKey(region: SpectrumRegion): string {
  return JSON.stringify([
    stableNumber(region.startTime), stableNumber(region.endTime),
    stableNumber(region.minMidi), stableNumber(region.maxMidi),
    region.pixelWidth, region.pixelHeight, stableNumber(region.threshold),
  ]);
}

type FetchRegion<T> = (region: SpectrumRegion) => Promise<T>;

export class DirectSpectrumRegionCache<T = DirectSpectrumPayload> {
  private readonly cache = new Map<string, T>();
  private readonly inflight = new Map<string, Promise<T | null>>();
  private readonly fetchRegion: FetchRegion<T>;
  private readonly maxEntries: number;
  private generation = 0;
  readonly stats = { backendQueries: 0, cacheHits: 0, deduplicatedQueries: 0, staleResults: 0 };

  constructor(fetchRegion: FetchRegion<T>, maxEntries = 2) {
    this.fetchRegion = fetchRegion;
    this.maxEntries = maxEntries;
  }

  invalidate(): void {
    this.generation += 1;
    this.cache.clear();
    this.inflight.clear();
  }

  peek(region: SpectrumRegion): T | undefined {
    const key = spectrumRegionKey(region);
    const payload = this.cache.get(key);
    if (payload) {
      this.cache.delete(key);
      this.cache.set(key, payload);
      this.stats.cacheHits += 1;
    }
    return payload;
  }

  load(region: SpectrumRegion): Promise<T | null> {
    const cached = this.peek(region);
    if (cached) return Promise.resolve(cached);

    const key = spectrumRegionKey(region);
    const pending = this.inflight.get(key);
    if (pending) {
      this.stats.deduplicatedQueries += 1;
      return pending;
    }

    const requestGeneration = this.generation;
    this.stats.backendQueries += 1;
    const request = this.fetchRegion(region).then(payload => {
      if (requestGeneration !== this.generation) {
        this.stats.staleResults += 1;
        return null;
      }
      this.cache.set(key, payload);
      while (this.cache.size > this.maxEntries) {
        const oldest = this.cache.keys().next().value as string | undefined;
        if (oldest === undefined) break;
        this.cache.delete(oldest);
      }
      return payload;
    }).finally(() => {
      if (this.inflight.get(key) === request) this.inflight.delete(key);
    });
    this.inflight.set(key, request);
    return request;
  }

  prefetch(region: SpectrumRegion): void {
    void this.load(region).catch(() => { /* The foreground load reports actionable errors. */ });
  }
}
