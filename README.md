# Order Book

A limit order matching engine: two order books (bids and asks), price-time
priority matching, and cancel support.

## Running it

```bash
pip install -r requirements-dev.txt   # pytest, pytest-benchmark
python3 main.py                       # demo: runs the assignment's own worked example
pytest -q                             # correctness tests (test_engine.py)
```

Benchmarks and the load generator are separate, since they're slow and not
meant to run on every test invocation:

```bash
pytest bench_engine.py --benchmark-save=<tag>       # micro-benchmarks (add/cancel/match)
pytest bench_engine.py --benchmark-compare=<tag>    # ... after a change, compare against it
python3 load_test.py --ops 200000                   # end-to-end throughput
python3 load_test.py --ops 20000 --profile          # same, plus a cProfile breakdown
```

## API example

```python
from engine import MatchingEngine
from models import Side

engine = MatchingEngine()

sell_id, _ = engine.place_order(Side.SELL, 99, 5)
engine.place_order(Side.SELL, 101, 5)

buy_id, trades = engine.place_order(Side.BUY, 102, 8)
# trades: buy_id buys 5 @ 99 from sell_id (fully filled), then 3 @ 101 from
# the second sell order (which now rests on the book with quantity=2).

engine.best_bid(), engine.best_ask()   # None, 101
engine.top_levels(5)                   # ([], [(101, 2)])
engine.cancel(buy_id)                  # False — buy_id fully filled, nothing left to cancel
```

`place_order()` assigns the order an id, submits it, and returns
`(order_id, trades)` — the trades produced immediately, plus the id needed
to `cancel()` it later if any of it is still resting. If the order isn't
fully filled, the remainder rests on the book at its limit price.

If you already have a fully-formed `Order` (its own id included — useful
for tests, or a caller that manages its own id scheme), `submit(order)` is
the lower-level primitive `place_order` is built on; it returns just the
trades.

## Design choices and trade-offs

- **Matching**: price priority first, then time priority (FIFO) within a
  price level. A trade always executes at the *resting* order's price, not
  the incoming order's — standard price-time priority behavior.
- **Prices are integers.** Comparing and heap-ordering floats for something
  used as a sort/equality key invites the usual float-equality problems;
  integers (ticks) sidestep that.
- **`submit()` mutates the `Order` passed in** — its `quantity` becomes
  whatever's left unfilled after matching. This is intentional: the caller
  can inspect `order.quantity` after the call to see how much remains, or
  copy the order first if they want the original request preserved.
- **Two entry points for submitting an order.** `place_order(side, price,
  quantity)` is the one the spec asks for: it assigns the id (an
  incrementing counter) and returns `(order_id, trades)`. `submit(order)`
  underneath it takes an already-built `Order` with its own id — used
  internally by `place_order`, and directly by tests that need specific
  ids to express FIFO ordering. Mixing the two — an `Order` with an id
  that collides with the counter's next value — is undefined.
- **Invalid orders are rejected early.** `submit()` (and so `place_order`)
  raises `ValueError` on a negative price or quantity, before it can reach
  the book. Zero is allowed and is a no-op (matches nothing, rests nothing).
- **`top_levels(n)` reports total quantity per price level**, not just the
  price: `(price, sum of resting quantity at that price)` for the best `n`
  levels per side. It reads the price-level dicts' keys directly (always
  exactly the live prices — the invariant lazy heap cleanup already
  depends on) via `heapq.nlargest`/`nsmallest`, which is O(levels log n)
  rather than sorting every level just to take the first `n`.
- **`cancel()` is O(1)**: an `order_id -> Node` index gives direct access to
  the resting order, and each price level is an intrusive doubly linked
  list (`Node`/`PriceLevel`, with sentinel head/tail nodes) so the node can
  be spliced out without scanning anything. An earlier version scanned the
  whole book by id instead; see `bench_results/engine_1.0_vs_2.0_*` for the
  measured before/after (cancel at 20,000 resting orders: ~0.7-1.5ms down
  to ~8µs).
- **Price-level heaps are cleaned up lazily.** Deleting an empty price
  level only removes its dict entry; the matching heap entry is left in
  place and discarded the next time `best_bid`/`best_ask` is called and
  finds it stale, rather than rebuilding the heap on every cancel/fill.
- **`trade_history()`** returns every `Trade` the engine has ever produced,
  in execution order — a minimal fills tape, beyond what the spec asks for
  but a natural extension of trade reporting.
- **Scope**: plain limit orders only. No market orders, no time-in-force
  variants (IOC/FOK), no order modification (cancel and resubmit instead).

## Testing

- `test_engine.py` — deterministic tests for an empty book, non-crossing
  orders, exact and partial fills, multi-level sweeps, price/time
  priority, FIFO (including partial fills and cancels mid-queue), cancel
  (missing id, double-cancel, cancel of an already-filled order,
  cancelling the best price and confirming the next level takes over),
  `place_order`'s id assignment (unique, increasing, usable to `cancel()`,
  matching the ids in the resulting `Trade`s), `top_levels` (quantity per
  level, price ordering on both sides, `n` larger than the book, empty
  book), input validation, `trade_history`, and the exact example from the
  assignment sheet, reproduced as a test.

  Every test that changes book structure re-checks that `best_bid`/
  `best_ask` match the actual best of the live price levels, that no price
  level is left empty, and that the book is never crossed
  (`assert_book_consistent`). This is checked behaviorally rather than by
  comparing raw heap contents to the price-level dicts, since lazy heap
  cleanup means the two aren't required to match exactly between queries.
- A **randomized property test**, in the same file, runs 20 fixed seeds of
  300 random submit/cancel operations each, checking that invariant after
  every single operation and that quantity is conserved
  (`submitted == 2 × traded + resting + cancelled`) at the end. This is
  what actually caught a heap/dict desync bug in an earlier version that
  the deterministic tests happened not to reach.

## Extras

- `bench_engine.py` — `pytest-benchmark` scenarios for `add`/`cancel`/
  `_match` at increasing book sizes, saved and compared across versions.
- `load_test.py` — a synthetic end-to-end load generator reporting
  throughput, with an optional `cProfile` breakdown of where time goes.
- `bench_results/` — captured throughput/profile snapshots per version
  (`engine_1.0_*`, `engine_2.0_linkedlist_*`), plus
  `engine_1.0_vs_2.0_summary.txt` and `..._benchmark_summary.txt` comparing
  them directly, so a performance claim always has a rerunnable number
  behind it rather than being asserted in prose.
- `repr(orderbook)` — prints a small ladder (best few levels, asks over
  bids) for quick inspection while debugging or demoing; see `main.py`.

Anything the spec leaves open was a deliberate call, noted above rather
than left implicit.
