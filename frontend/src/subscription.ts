/**
 * One shared `parcels/subscribe` subscription per Home Assistant connection,
 * reference-counted across all cards on the page.
 */
import { errorMessage } from "./errors.ts";
import { normalizeSnapshot } from "./normalize.ts";
import type { HassConnection, HassUnsubscribe, Snapshot } from "./types.ts";

export interface SnapshotState {
  snapshot: Snapshot | null;
  /** The last subscribe error; cleared by the next snapshot. */
  error: string | null;
}

export type SnapshotListener = (state: SnapshotState) => void;

export const SUBSCRIBE_TYPE = "parcels/subscribe";

/** Waits before retrying a failed subscribe (the last one repeats). */
export const RETRY_DELAYS_MS: readonly number[] = [2_000, 10_000, 30_000, 60_000, 300_000];

interface Entry {
  readonly connection: HassConnection;
  readonly listeners: Map<number, SnapshotListener>;
  state: SnapshotState;
  /** Bumped on every disconnect; subscriptions of an older epoch died with their socket. */
  epoch: number;
  /** Bumped on every subscribe attempt, disconnect and release, so stale results are ignored. */
  attempt: number;
  unsubscribe: HassUnsubscribe | null;
  pending: boolean;
  released: boolean;
  retries: number;
  retryTimer: ReturnType<typeof setTimeout> | undefined;
  readonly onReady: () => void;
  readonly onDisconnected: () => void;
}

const entries = new Map<HassConnection, Entry>();
let nextToken = 0;

function notify(listener: SnapshotListener, state: SnapshotState): void {
  try {
    listener(state);
  } catch (error) {
    console.error(error);
  }
}

function setState(entry: Entry, state: SnapshotState): void {
  entry.state = state;
  // Copy: a listener may unsubscribe while it's being notified.
  // oxlint-disable-next-line unicorn/no-useless-spread
  for (const listener of [...entry.listeners.values()]) {
    notify(listener, state);
  }
}

function endSubscription(unsubscribe: HassUnsubscribe): void {
  try {
    unsubscribe().catch(() => undefined);
  } catch {
    // Nothing to clean up if it can't be ended.
  }
}

function clearRetry(entry: Entry): void {
  if (entry.retryTimer !== undefined) {
    clearTimeout(entry.retryTimer);
    entry.retryTimer = undefined;
  }
}

function detach(entry: Entry): void {
  entry.connection.removeEventListener("ready", entry.onReady);
  entry.connection.removeEventListener("disconnected", entry.onDisconnected);
}

function scheduleRetry(entry: Entry): void {
  clearRetry(entry);
  const delay =
    RETRY_DELAYS_MS[Math.min(entry.retries, RETRY_DELAYS_MS.length - 1)] ?? 300_000;
  entry.retries += 1;
  entry.retryTimer = setTimeout(() => {
    entry.retryTimer = undefined;
    start(entry);
  }, delay);
}

function start(entry: Entry): void {
  if (entry.released || entry.unsubscribe || entry.pending || entry.listeners.size === 0) {
    return;
  }
  clearRetry(entry);
  const attempt = ++entry.attempt;
  const epoch = entry.epoch;
  const isCurrent = (): boolean => !entry.released && entry.attempt === attempt;
  entry.pending = true;
  let request: Promise<HassUnsubscribe>;
  try {
    request = entry.connection.subscribeMessage<unknown>(
      (message) => {
        if (isCurrent()) {
          entry.retries = 0;
          setState(entry, { snapshot: normalizeSnapshot(message), error: null });
        }
      },
      { type: SUBSCRIBE_TYPE },
      // Resubscribing is done here on "ready", so that a failure (e.g. while
      // Home Assistant is still starting) is retried instead of lost.
      { resubscribe: false },
    );
  } catch (error) {
    request = Promise.reject(error);
  }
  request.then(
    (unsubscribe) => {
      if (isCurrent()) {
        entry.pending = false;
        entry.unsubscribe = unsubscribe;
        return;
      }
      // Nobody needs this subscription any more. End it only while its socket
      // is still open: after a reconnect, command IDs start over and the old ID
      // may belong to another subscription.
      if (entry.epoch === epoch) {
        endSubscription(unsubscribe);
      }
      if (entry.released && entry.attempt === attempt + 1) {
        entry.pending = false;
        detach(entry);
      }
    },
    (error: unknown) => {
      if (isCurrent()) {
        entry.pending = false;
        setState(entry, { snapshot: entry.state.snapshot, error: errorMessage(error) });
        scheduleRetry(entry);
      } else if (entry.released && entry.attempt === attempt + 1) {
        entry.pending = false;
        detach(entry);
      }
    },
  );
}

function release(entry: Entry, token: number): void {
  if (!entry.listeners.delete(token) || entry.listeners.size > 0) {
    return;
  }
  entry.released = true;
  entry.attempt += 1;
  clearRetry(entry);
  if (entries.get(entry.connection) === entry) {
    entries.delete(entry.connection);
  }
  const unsubscribe = entry.unsubscribe;
  entry.unsubscribe = null;
  if (unsubscribe) {
    endSubscription(unsubscribe);
  }
  // With a subscribe still in flight, keep listening for a disconnect until it
  // settles, so that it's only ended while its socket is still open.
  if (!entry.pending) {
    detach(entry);
  }
}

function createEntry(connection: HassConnection): Entry {
  const entry: Entry = {
    connection,
    listeners: new Map(),
    state: { snapshot: null, error: null },
    epoch: 0,
    attempt: 0,
    unsubscribe: null,
    pending: false,
    released: false,
    retries: 0,
    retryTimer: undefined,
    onReady: () => {
      if (entry.released || entry.unsubscribe) {
        return;
      }
      // An attempt made while the socket was down may never settle; start over.
      entry.pending = false;
      entry.retries = 0;
      start(entry);
    },
    onDisconnected: () => {
      entry.epoch += 1;
      entry.attempt += 1;
      entry.unsubscribe = null;
      entry.pending = false;
      clearRetry(entry);
      if (entry.released) {
        detach(entry);
      }
    },
  };
  return entry;
}

/**
 * Calls `listener` with every snapshot of the shared subscription for this
 * connection (right away with the latest one when there is one). Returns a
 * function that stops listening; the subscription ends with its last listener.
 */
export function subscribeSnapshot(
  connection: HassConnection,
  listener: SnapshotListener,
): () => void {
  const token = ++nextToken;
  let entry = entries.get(connection);
  if (entry) {
    entry.listeners.set(token, listener);
    if (entry.state.snapshot || entry.state.error) {
      notify(listener, entry.state);
    }
  } else {
    entry = createEntry(connection);
    entries.set(connection, entry);
    entry.listeners.set(token, listener);
    connection.addEventListener("ready", entry.onReady);
    connection.addEventListener("disconnected", entry.onDisconnected);
    start(entry);
  }
  const owner = entry;
  let subscribed = true;
  return () => {
    if (subscribed) {
      subscribed = false;
      release(owner, token);
    }
  };
}

/** Number of connections with a shared subscription (for tests). */
export function sharedSubscriptionCount(): number {
  return entries.size;
}
