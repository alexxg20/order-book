"""pytest-benchmark scenarios for MatchingEngine.

Not collected by a plain `pytest -q` run — run explicitly:

    pytest bench_engine.py --benchmark-save=<tag>
    # ... change engine.py ...
    pytest bench_engine.py --benchmark-compare=<tag>

Book sizes go up to 20_000 so cost-vs-book-size trends are visible, whatever
shape they turn out to have; rounds are scaled down as the book grows so
setup cost (excluded from the measurement, but not from wall-clock) stays
bounded.
"""
import itertools

import pytest

from engine import MatchingEngine
from test_engine import buy, sell

BOOK_SIZES = [100, 1_000, 5_000, 20_000]


def _rounds_for(n):
    return max(8, min(30, 20_000 // n))


def _book_of_bids(n):
    """Engine with n resting bids, each its own price level, so a cancel
    benchmark can target a specific position within the book (first
    inserted, last inserted, or absent) at a known book size."""
    engine = MatchingEngine()
    for i in range(n):
        engine.submit(buy(i, 1000 + i, 1))
    return engine


# --- add() ----------------------------------------------------------------

@pytest.mark.parametrize("n", BOOK_SIZES)
def test_add_new_price_level(benchmark, n):
    """add() when the incoming price isn't on the book yet, at a given book size."""
    counter = itertools.count()

    def setup():
        order = buy(n + next(counter), 1000 + n, 1)  # fresh price, above all resting
        return (_book_of_bids(n).orderbook, order), {}

    def run(orderbook, order):
        orderbook.add(order)

    benchmark.pedantic(run, setup=setup, rounds=_rounds_for(n))


@pytest.mark.parametrize("n", BOOK_SIZES)
def test_add_existing_price_level(benchmark, n):
    """add() when the price level already exists, at a given book size."""
    orderbook = _book_of_bids(n).orderbook
    counter = itertools.count(n)

    def run():
        orderbook.add(buy(next(counter), 1000, 1))  # same price every call

    benchmark.pedantic(run, rounds=_rounds_for(n))


# --- cancel() ---------------------------------------------------------------

@pytest.mark.parametrize("n", BOOK_SIZES)
def test_cancel_first_order(benchmark, n):
    """Cancel the order that was added first, at a given book size."""
    def setup():
        return (_book_of_bids(n), 0), {}

    def run(engine, order_id):
        engine.cancel(order_id)

    benchmark.pedantic(run, setup=setup, rounds=_rounds_for(n))


@pytest.mark.parametrize("n", BOOK_SIZES)
def test_cancel_last_order(benchmark, n):
    """Cancel the order that was added last, at a given book size."""
    def setup():
        return (_book_of_bids(n), n - 1), {}

    def run(engine, order_id):
        engine.cancel(order_id)

    benchmark.pedantic(run, setup=setup, rounds=_rounds_for(n))


@pytest.mark.parametrize("n", BOOK_SIZES)
def test_cancel_missing_order(benchmark, n):
    """Cancel an id that was never on the book, at a given book size."""
    def setup():
        return (_book_of_bids(n), -1), {}

    def run(engine, order_id):
        engine.cancel(order_id)

    benchmark.pedantic(run, setup=setup, rounds=_rounds_for(n))


# --- _match() ---------------------------------------------------------------

def test_match_single_fill(benchmark):
    """One resting order, one incoming order that fills it exactly."""
    counter = itertools.count()

    def setup():
        engine = MatchingEngine()
        engine.submit(sell(next(counter), 100, 1))
        return (engine,), {}

    def run(engine):
        engine.submit(buy(next(counter), 100, 1))

    benchmark.pedantic(run, setup=setup, rounds=50)


@pytest.mark.parametrize("n", [10, 100, 1_000])
def test_match_sweep(benchmark, n):
    """One incoming order that sweeps n resting ask price levels before it rests or exhausts."""
    counter = itertools.count()

    def setup():
        engine = MatchingEngine()
        for i in range(n):
            engine.submit(sell(next(counter), 100 + i, 1))
        order = buy(next(counter), 100 + n, n)  # crosses every level exactly
        return (engine, order), {}

    def run(engine, order):
        engine.submit(order)

    benchmark.pedantic(run, setup=setup, rounds=_rounds_for(n) if n >= 100 else 30)
