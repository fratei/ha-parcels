/** Lit controller that follows the shared `parcels/subscribe` snapshot while its card is on the page. */
import type { ReactiveController, ReactiveControllerHost } from "lit";
import { subscribeSnapshot } from "./subscription.ts";
import type { HassConnection, Snapshot } from "./types.ts";

export class SnapshotController implements ReactiveController {
  /** The latest snapshot; kept while the subscription is retried. */
  snapshot: Snapshot | null = null;
  /** The last subscribe error, cleared by the next snapshot. */
  error: string | null = null;

  private readonly _host: ReactiveControllerHost;
  private _connection: HassConnection | null = null;
  private _unsubscribe: (() => void) | null = null;
  private _hostConnected = false;

  constructor(host: ReactiveControllerHost) {
    this._host = host;
    host.addController(this);
  }

  /** Follows the snapshot of another connection (or none). */
  setConnection(connection: HassConnection | null): void {
    if (connection === this._connection) {
      return;
    }
    this._release();
    this._connection = connection;
    this.snapshot = null;
    this.error = null;
    if (this._hostConnected) {
      this._subscribe();
    }
    this._host.requestUpdate();
  }

  hostConnected(): void {
    this._hostConnected = true;
    this._subscribe();
  }

  hostDisconnected(): void {
    this._hostConnected = false;
    this._release();
  }

  private _subscribe(): void {
    if (!this._connection || this._unsubscribe) {
      return;
    }
    this._unsubscribe = subscribeSnapshot(this._connection, (state) => {
      this.snapshot = state.snapshot ?? this.snapshot;
      this.error = state.error;
      this._host.requestUpdate();
    });
  }

  private _release(): void {
    const unsubscribe = this._unsubscribe;
    this._unsubscribe = null;
    unsubscribe?.();
  }
}
