# Order Book

A limit order matching engine: two order books (bids and asks), price-time
priority matching, and cancel support.

## Running it

```bash
pip install -r requirements-dev.txt   # pytest, pytest-benchmark
python3 main.py                       # demo: a few orders, prints the resulting trades
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
from models import Order, Side

engine = MatchingEngine()

engine.submit(Order(order_id=1, side=Side.SELL, price=99, quantity=5))
engine.submit(Order(order_id=2, side=Side.SELL, price=101, quantity=5))

trades = engine.submit(Order(order_id=3, side=Side.BUY, price=102, quantity=8))
# trades: order 3 buys 5 @ 99 from order 1 (fully filled), then 3 @ 101 from
# order 2 (which now rests on the book with quantity=2).
```

`submit()` returns the list of `Trade`s produced immediately; if the order
isn't fully filled, the remainder rests on the book at its limit price.

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
- **Order ids are caller-assigned and assumed unique.** There's no
  auto-generation and no rejection of a duplicate id; passing one is
  undefined (the older order becomes unreachable by id).
- **`cancel()` currently does a linear scan** of the resting orders to find
  one by id — simple, but O(n) in book size. This is a known limitation,
  not an oversight, and it's what `bench_engine.py`'s cancel benchmarks
  exist to quantify; a rewrite to an id-indexed lookup is planned and the
  benchmark numbers are how it'll be checked, not just claimed.
- **Scope**: plain limit orders only. No market orders, no time-in-force
  variants (IOC/FOK), no order modification (cancel and resubmit instead).

## Testing

- `test_engine.py` — deterministic tests for an empty book, non-crossing
  orders, exact and partial fills, multi-level sweeps, price/time
  priority, FIFO (including partial fills and cancels mid-queue), and
  cancel (missing id, double-cancel, cancel of an already-filled order,
  cancelling the best price and confirming the next level takes over).
  Every test that changes book structure re-checks that the heaps and the
  price-level dicts still agree with each other and that the book is never
  crossed (`assert_book_consistent`).
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
- `bench_results/engine_1.0_*.txt` — a captured throughput/profile snapshot
  of this version, kept as a baseline to compare future versions against.

Anything not dictated by the spec (integer prices, mutating the caller's
order, FIFO tie-break, the resting-price-wins rule) was my own call, listed
above rather than left implicit.
