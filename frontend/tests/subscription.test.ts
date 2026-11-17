import assert from "node:assert/strict";
import { afterEach, describe, test } from "node:test";
import type { TestContext } from "node:test";

import {
  RETRY_DELAYS_MS,
  SUBSCRIBE_TYPE,
  sharedSubscriptionCount,
  subscribeSnapshot,
} from "../src/subscription.ts";
import type { SnapshotState } from "../src/subscription.ts";
import type {
  ConnectionEvent,
  HassConnection,
  HassMessage,
  HassUnsubscribe,
} from "../src/types.ts";
import { flush } from "./helpers.ts";

interface Call {
  message: HassMessage;
  options: { resubscribe?: boolean } | undefined;
  /** Sends an event to this subscription's callback. */
  emit(event: unknown): void;
  resolve(): void;
  reject(error: unknown): void;
  /** How many times its unsubscribe function was called. */
  unsubscribed: number;
}

/** Stands in for home-assistant-js-websocket's Connection; the test settles every call. */
class FakeConnection implements HassConnection {
  calls: Call[] = [];
  private readonly handlers = new Map<ConnectionEvent, Set<() => void>>();

  subscribeMessage<T>(
    callback: (message: T) => void,
    message: HassMessage,
    options?: { resubscribe?: boolean },
  ): Promise<HassUnsubscribe> {
    return new Promise((resolve, reject) => {
      const call: Call = {
        message,
        options,
        emit: (event) => callback(event as T),
        resolve: () =>
          resolve(async () => {
            call.unsubscribed += 1;
          }),
        reject,
        unsubscribed: 0,
      };
      this.calls.push(call);
    });
  }

  addEventListener(event: ConnectionEvent, listener: () => void): void {
    let set = this.handlers.get(event);
    if (!set) {
      set = new Set();
      this.handlers.set(event, set);
    }
    set.add(listener);
  }

  removeEventListener(event: ConnectionEvent, listener: () => void): void {
    this.handlers.get(event)?.delete(listener);
  }

  fire(event: ConnectionEvent): void {
    // Copy: a listener may remove itself while it's being called.
    // oxlint-disable-next-line unicorn/no-useless-spread
    for (const listener of [...(this.handlers.get(event) ?? [])]) {
      listener();
    }
  }

  listenerCount(): number {
    let count = 0;
    for (const set of this.handlers.values()) {
      count += set.size;
    }
    return count;
  }

  call(index: number): Call {
    const call = this.calls[index];
    assert.ok(call, `subscribe call ${index} was made`);
    return call;
  }
}

function snapshotEvent(merchant: string): unknown {
  return {
    parcels: [{ id: "p1", status: "shipped", merchant }],
    review: [],
    filtered: [],
    settings: { time_zone: "Europe/Lisbon", today: "2026-07-15", user_is_admin: true },
  };
}

/** A listener that records every state it gets. */
function recorder(): { states: SnapshotState[]; listener: (state: SnapshotState) => void } {
  const states: SnapshotState[] = [];
  return { states, listener: (state) => states.push(state) };
}

function merchants(states: SnapshotState[]): Array<string | null> {
  return states.map((state) => state.snapshot?.parcels[0]?.merchant ?? null);
}

function useFakeTimers(t: TestContext): void {
  t.mock.timers.enable({ apis: ["setTimeout"] });
}

afterEach(() => {
  assert.equal(sharedSubscriptionCount(), 0, "every test releases its subscriptions");
});

describe("shared subscription", () => {
  test("is shared by every listener on a connection", async () => {
    const connection = new FakeConnection();
    const first = recorder();
    const second = recorder();
    const releaseFirst = subscribeSnapshot(connection, first.listener);
    const releaseSecond = subscribeSnapshot(connection, second.listener);
    assert.equal(connection.calls.length, 1);
    assert.deepEqual(connection.call(0).message, { type: SUBSCRIBE_TYPE });
    assert.deepEqual(connection.call(0).options, { resubscribe: false });
    assert.equal(sharedSubscriptionCount(), 1);

    connection.call(0).resolve();
    await flush();
    connection.call(0).emit(snapshotEvent("Example Shop"));
    assert.deepEqual(merchants(first.states), ["Example Shop"]);
    assert.deepEqual(merchants(second.states), ["Example Shop"]);
    assert.equal(first.states[0]?.error, null);

    releaseFirst();
    assert.equal(connection.call(0).unsubscribed, 0);
    connection.call(0).emit(snapshotEvent("Test Store"));
    assert.deepEqual(merchants(first.states), ["Example Shop"]);
    assert.deepEqual(merchants(second.states), ["Example Shop", "Test Store"]);

    releaseSecond();
    assert.equal(connection.call(0).unsubscribed, 1);
    assert.equal(connection.listenerCount(), 0);
    assert.equal(connection.calls.length, 1);
  });

  test("gives a late listener the latest snapshot right away", async () => {
    const connection = new FakeConnection();
    const first = recorder();
    const late = recorder();
    const releaseFirst = subscribeSnapshot(connection, first.listener);
    connection.call(0).resolve();
    await flush();
    connection.call(0).emit(snapshotEvent("Example Shop"));
    const releaseLate = subscribeSnapshot(connection, late.listener);
    assert.deepEqual(merchants(late.states), ["Example Shop"]);
    assert.equal(connection.calls.length, 1);
    releaseFirst();
    releaseLate();
    assert.equal(connection.call(0).unsubscribed, 1);
  });

  test("doesn't notify a new listener before there is anything to tell", () => {
    const connection = new FakeConnection();
    const first = recorder();
    const second = recorder();
    const releaseFirst = subscribeSnapshot(connection, first.listener);
    const releaseSecond = subscribeSnapshot(connection, second.listener);
    assert.equal(second.states.length, 0);
    releaseFirst();
    releaseSecond();
  });

  test("releasing twice only counts once", async () => {
    const connection = new FakeConnection();
    const releaseFirst = subscribeSnapshot(connection, recorder().listener);
    const releaseSecond = subscribeSnapshot(connection, recorder().listener);
    connection.call(0).resolve();
    await flush();
    releaseFirst();
    releaseFirst();
    assert.equal(connection.call(0).unsubscribed, 0);
    assert.equal(sharedSubscriptionCount(), 1);
    releaseSecond();
    releaseSecond();
    assert.equal(connection.call(0).unsubscribed, 1);
  });

  test("counts the same listener function twice when it's added twice", async () => {
    const connection = new FakeConnection();
    const { states, listener } = recorder();
    const releaseFirst = subscribeSnapshot(connection, listener);
    const releaseSecond = subscribeSnapshot(connection, listener);
    connection.call(0).resolve();
    await flush();
    releaseFirst();
    connection.call(0).emit(snapshotEvent("Example Shop"));
    assert.deepEqual(merchants(states), ["Example Shop"]);
    releaseSecond();
    assert.equal(connection.call(0).unsubscribed, 1);
  });

  test("keeps one subscription per connection", async () => {
    const one = new FakeConnection();
    const two = new FakeConnection();
    const releaseOne = subscribeSnapshot(one, recorder().listener);
    const releaseTwo = subscribeSnapshot(two, recorder().listener);
    assert.equal(one.calls.length, 1);
    assert.equal(two.calls.length, 1);
    assert.equal(sharedSubscriptionCount(), 2);
    one.call(0).resolve();
    two.call(0).resolve();
    await flush();
    releaseOne();
    assert.equal(one.call(0).unsubscribed, 1);
    assert.equal(two.call(0).unsubscribed, 0);
    releaseTwo();
    assert.equal(two.call(0).unsubscribed, 1);
  });

  test("subscribes again after the last listener left and a new one came", async () => {
    const connection = new FakeConnection();
    subscribeSnapshot(connection, recorder().listener)();
    const release = subscribeSnapshot(connection, recorder().listener);
    assert.equal(connection.calls.length, 2);
    connection.call(0).resolve();
    connection.call(1).resolve();
    await flush();
    assert.equal(connection.call(0).unsubscribed, 1);
    assert.equal(connection.call(1).unsubscribed, 0);
    release();
    assert.equal(connection.call(1).unsubscribed, 1);
    assert.equal(connection.listenerCount(), 0);
  });

  test("normalizes every snapshot", async () => {
    const connection = new FakeConnection();
    const { states, listener } = recorder();
    const release = subscribeSnapshot(connection, listener);
    connection.call(0).resolve();
    await flush();
    connection.call(0).emit({ parcels: [{ id: "p1" }, { nope: true }], settings: { today: "2026-07-15" } });
    const snapshot = states[0]?.snapshot;
    assert.ok(snapshot);
    assert.equal(snapshot.parcels.length, 1);
    assert.deepEqual(snapshot.review, []);
    assert.equal(snapshot.settings.today, "2026-07-15");
    assert.equal(snapshot.settings.user_is_admin, false);
    release();
  });

  test("ignores events after the last listener left", async () => {
    const connection = new FakeConnection();
    const { states, listener } = recorder();
    const release = subscribeSnapshot(connection, listener);
    connection.call(0).resolve();
    await flush();
    release();
    connection.call(0).emit(snapshotEvent("Example Shop"));
    assert.equal(states.length, 0);
  });

  test("keeps notifying when one listener throws", async (t) => {
    const errors = t.mock.method(console, "error", () => undefined);
    const connection = new FakeConnection();
    const good = recorder();
    const releaseBad = subscribeSnapshot(connection, () => {
      throw new Error("broken card");
    });
    const releaseGood = subscribeSnapshot(connection, good.listener);
    connection.call(0).resolve();
    await flush();
    connection.call(0).emit(snapshotEvent("Example Shop"));
    assert.deepEqual(merchants(good.states), ["Example Shop"]);
    assert.equal(errors.mock.callCount(), 1);
    releaseBad();
    releaseGood();
  });
});

describe("reconnecting", () => {
  test("subscribes again after a reconnect and never ends the old subscription", async () => {
    const connection = new FakeConnection();
    const { states, listener } = recorder();
    const release = subscribeSnapshot(connection, listener);
    connection.call(0).resolve();
    await flush();
    connection.call(0).emit(snapshotEvent("Example Shop"));

    connection.fire("disconnected");
    connection.call(0).emit(snapshotEvent("Stale Shop"));
    assert.deepEqual(merchants(states), ["Example Shop"]);
    assert.equal(connection.calls.length, 1);

    connection.fire("ready");
    assert.equal(connection.calls.length, 2);
    connection.call(1).resolve();
    await flush();
    connection.call(1).emit(snapshotEvent("Test Store"));
    assert.deepEqual(merchants(states), ["Example Shop", "Test Store"]);

    release();
    // Command IDs start over on a new socket, so the old unsubscribe could end someone else's subscription.
    assert.equal(connection.call(0).unsubscribed, 0);
    assert.equal(connection.call(1).unsubscribed, 1);
    assert.equal(connection.listenerCount(), 0);
  });

  test("starts over when a subscribe was in flight during the disconnect", async () => {
    const connection = new FakeConnection();
    const { states, listener } = recorder();
    const release = subscribeSnapshot(connection, listener);
    connection.fire("disconnected");
    connection.fire("ready");
    assert.equal(connection.calls.length, 2);
    // The first one would normally never settle; if it does, it belongs to a dead socket.
    connection.call(0).resolve();
    connection.call(1).resolve();
    await flush();
    connection.call(0).emit(snapshotEvent("Stale Shop"));
    connection.call(1).emit(snapshotEvent("Example Shop"));
    assert.deepEqual(merchants(states), ["Example Shop"]);
    release();
    assert.equal(connection.call(0).unsubscribed, 0);
    assert.equal(connection.call(1).unsubscribed, 1);
  });

  test("ends a duplicate that settles on the same socket", async () => {
    // The card started while the socket was already down, so it never saw "disconnected".
    const connection = new FakeConnection();
    const release = subscribeSnapshot(connection, recorder().listener);
    connection.fire("ready");
    assert.equal(connection.calls.length, 2);
    connection.call(0).resolve();
    connection.call(1).resolve();
    await flush();
    assert.equal(connection.call(0).unsubscribed, 1);
    assert.equal(connection.call(1).unsubscribed, 0);
    release();
    assert.equal(connection.call(1).unsubscribed, 1);
  });

  test("keeps the last snapshot when subscribing again fails", async (t) => {
    useFakeTimers(t);
    const connection = new FakeConnection();
    const { states, listener } = recorder();
    const release = subscribeSnapshot(connection, listener);
    connection.call(0).resolve();
    await flush();
    connection.call(0).emit(snapshotEvent("Example Shop"));
    connection.fire("disconnected");
    connection.fire("ready");
    connection.call(1).reject({ code: "home_assistant_error", message: "Home Assistant is starting" });
    await flush();
    const last = states.at(-1);
    assert.equal(last?.error, "Home Assistant is starting");
    assert.equal(last?.snapshot?.parcels[0]?.merchant, "Example Shop");
    release();
  });
});

describe("releasing during a subscribe", () => {
  test("ends the subscription once it's made", async () => {
    const connection = new FakeConnection();
    const release = subscribeSnapshot(connection, recorder().listener);
    release();
    assert.equal(sharedSubscriptionCount(), 0);
    assert.equal(connection.listenerCount(), 2, "still watching for a disconnect");
    connection.call(0).resolve();
    await flush();
    assert.equal(connection.call(0).unsubscribed, 1);
    assert.equal(connection.listenerCount(), 0);
  });

  test("never ends it after a disconnect", async () => {
    const connection = new FakeConnection();
    const release = subscribeSnapshot(connection, recorder().listener);
    release();
    connection.fire("disconnected");
    assert.equal(connection.listenerCount(), 0);
    connection.call(0).resolve();
    await flush();
    assert.equal(connection.call(0).unsubscribed, 0);
  });

  test("stops listening when the subscribe fails", async () => {
    const connection = new FakeConnection();
    const { states, listener } = recorder();
    const release = subscribeSnapshot(connection, listener);
    release();
    connection.call(0).reject({ code: "unknown_command", message: "Unknown command." });
    await flush();
    assert.equal(connection.listenerCount(), 0);
    assert.equal(states.length, 0);
  });
});

describe("errors", () => {
  test("are reported and retried with a growing delay", async (t) => {
    useFakeTimers(t);
    const connection = new FakeConnection();
    const { states, listener } = recorder();
    const release = subscribeSnapshot(connection, listener);
    connection.call(0).reject({ code: "unknown_command", message: "Unknown command." });
    await flush();
    // A copy, so that the assertion doesn't narrow the type of `states`.
    assert.deepEqual(states.slice(), [{ snapshot: null, error: "Unknown command." }]);

    const [first = 0, second = 0] = RETRY_DELAYS_MS;
    t.mock.timers.tick(first - 1);
    assert.equal(connection.calls.length, 1);
    t.mock.timers.tick(1);
    assert.equal(connection.calls.length, 2);

    connection.call(1).reject(new Error("Still starting"));
    await flush();
    assert.equal(states.at(-1)?.error, "Still starting");
    t.mock.timers.tick(second - 1);
    assert.equal(connection.calls.length, 2);
    t.mock.timers.tick(1);
    assert.equal(connection.calls.length, 3);

    connection.call(2).resolve();
    await flush();
    connection.call(2).emit(snapshotEvent("Example Shop"));
    assert.equal(states.at(-1)?.error, null);
    assert.equal(states.at(-1)?.snapshot?.parcels[0]?.merchant, "Example Shop");

    // A late listener sees the snapshot, not the old error.
    const late = recorder();
    const releaseLate = subscribeSnapshot(connection, late.listener);
    assert.equal(late.states[0]?.error, null);
    releaseLate();
    release();
    assert.equal(connection.call(2).unsubscribed, 1);
  });

  test("keep the longest delay once the delays run out", async (t) => {
    useFakeTimers(t);
    const connection = new FakeConnection();
    const release = subscribeSnapshot(connection, recorder().listener);
    const longest = RETRY_DELAYS_MS.at(-1) ?? 0;
    for (let index = 0; index < RETRY_DELAYS_MS.length + 2; index += 1) {
      connection.call(index).reject({ message: "Unknown command." });
      await flush();
      const delay = RETRY_DELAYS_MS[index] ?? longest;
      t.mock.timers.tick(delay - 1);
      assert.equal(connection.calls.length, index + 1);
      t.mock.timers.tick(1);
      assert.equal(connection.calls.length, index + 2);
    }
    release();
  });

  test("tell a late listener about the error", async () => {
    const connection = new FakeConnection();
    const release = subscribeSnapshot(connection, recorder().listener);
    connection.call(0).reject({ message: "Unknown command." });
    await flush();
    const late = recorder();
    const releaseLate = subscribeSnapshot(connection, late.listener);
    assert.deepEqual(late.states, [{ snapshot: null, error: "Unknown command." }]);
    releaseLate();
    release();
  });

  test("retry right away when the connection comes back", async (t) => {
    useFakeTimers(t);
    const connection = new FakeConnection();
    const release = subscribeSnapshot(connection, recorder().listener);
    connection.call(0).reject({ message: "Connection lost" });
    await flush();
    connection.fire("disconnected");
    connection.fire("ready");
    assert.equal(connection.calls.length, 2);
    t.mock.timers.tick(RETRY_DELAYS_MS[0] ?? 0);
    assert.equal(connection.calls.length, 2, "the pending retry was cancelled");
    release();
  });

  test("are not retried once the last listener left", async (t) => {
    useFakeTimers(t);
    const connection = new FakeConnection();
    const release = subscribeSnapshot(connection, recorder().listener);
    connection.call(0).reject({ message: "Unknown command." });
    await flush();
    release();
    t.mock.timers.tick(RETRY_DELAYS_MS.at(-1) ?? 0);
    assert.equal(connection.calls.length, 1);
    assert.equal(connection.listenerCount(), 0);
  });

  test("of a throwing subscribeMessage are handled too", async (t) => {
    useFakeTimers(t);
    const connection = new FakeConnection();
    let throwNext = true;
    const original = connection.subscribeMessage.bind(connection);
    connection.subscribeMessage = <T>(
      callback: (message: T) => void,
      message: HassMessage,
      options?: { resubscribe?: boolean },
    ): Promise<HassUnsubscribe> => {
      if (throwNext) {
        throwNext = false;
        throw new Error("Socket closing");
      }
      return original(callback, message, options);
    };
    const { states, listener } = recorder();
    const release = subscribeSnapshot(connection, listener);
    await flush();
    assert.deepEqual(states, [{ snapshot: null, error: "Socket closing" }]);
    t.mock.timers.tick(RETRY_DELAYS_MS[0] ?? 0);
    assert.equal(connection.calls.length, 1);
    release();
  });
});
