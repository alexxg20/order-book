"""
Tests for MatchingEngine / OrderBook.
"""
import random

import pytest

from engine import MatchingEngine
from models import Order, Side, Trade


def buy(order_id, price, quantity):
    return Order(order_id=order_id, side=Side.BUY, price=price, quantity=quantity)


def sell(order_id, price, quantity):
    return Order(order_id=order_id, side=Side.SELL, price=price, quantity=quantity)


@pytest.fixture
def engine():
    return MatchingEngine()


def resting_ids(levels, price):
    """Order ids queued at a price level; returns [] rather than raising when the price isn't resting."""
    return [o.order_id for o in levels.get(price, [])]


def assert_book_consistent(engine):
    """Heaps and dicts must describe the same set of price levels, with no empty or duplicate levels."""
    book = engine.orderbook
    assert sorted(-p for p in book.bid_prices) == sorted(book.bids.keys())
    assert sorted(book.ask_prices) == sorted(book.asks.keys())
    assert all(len(q) > 0 for q in book.bids.values())
    assert all(len(q) > 0 for q in book.asks.values())
    assert all(o.quantity > 0 for q in book.bids.values() for o in q)
    assert all(o.quantity > 0 for q in book.asks.values() for o in q)
    if book.bids and book.asks:
        assert book.best_bid() < book.best_ask(), "book is crossed"


# --- empty book / empty orders -------------------------------------------------

def test_empty_book_has_no_best_prices(engine):
    assert engine.orderbook.best_bid() is None
    assert engine.orderbook.best_ask() is None


@pytest.mark.parametrize("make", [buy, sell])
def test_zero_quantity_order_is_a_noop(engine, make):
    trades = engine.submit(make(1, 100, 0))
    assert trades == []
    assert engine.orderbook.best_bid() is None
    assert engine.orderbook.best_ask() is None
    assert engine.cancel(1) is False


def test_zero_quantity_order_does_not_trade_against_resting(engine):
    engine.submit(sell(1, 100, 5))
    assert engine.submit(buy(2, 100, 0)) == []
    assert engine.orderbook.asks[100][0].quantity == 5


def test_order_into_empty_book_rests(engine):
    assert engine.submit(buy(1, 100, 10)) == []
    assert engine.orderbook.best_bid() == 100
    assert engine.orderbook.best_ask() is None
    assert_book_consistent(engine)


# --- orders that don't cross ---------------------------------------------------

def test_non_crossing_orders_both_rest(engine):
    assert engine.submit(buy(1, 99, 10)) == []
    assert engine.submit(sell(2, 101, 10)) == []
    assert engine.orderbook.best_bid() == 99
    assert engine.orderbook.best_ask() == 101
    assert_book_consistent(engine)


def test_buy_below_best_ask_does_not_trade(engine):
    engine.submit(sell(1, 100, 10))
    assert engine.submit(buy(2, 99, 10)) == []
    assert engine.orderbook.best_ask() == 100
    assert engine.orderbook.best_bid() == 99


def test_sell_above_best_bid_does_not_trade(engine):
    engine.submit(buy(1, 100, 10))
    assert engine.submit(sell(2, 101, 10)) == []
    assert engine.orderbook.best_bid() == 100
    assert engine.orderbook.best_ask() == 101


# --- exact fills ---------------------------------------------------------------

def test_exact_fill_buy_aggressor(engine):
    engine.submit(sell(1, 100, 10))
    trades = engine.submit(buy(2, 100, 10))
    assert trades == [Trade(buy_order_id=2, sell_order_id=1, price=100, quantity=10)]
    assert engine.orderbook.best_ask() is None
    assert engine.orderbook.best_bid() is None
    assert_book_consistent(engine)


def test_exact_fill_sell_aggressor(engine):
    engine.submit(buy(1, 100, 10))
    trades = engine.submit(sell(2, 100, 10))
    assert trades == [Trade(buy_order_id=1, sell_order_id=2, price=100, quantity=10)]
    assert engine.orderbook.best_ask() is None
    assert engine.orderbook.best_bid() is None
    assert_book_consistent(engine)


def test_exact_fill_deletes_ask_price_key(engine):
    engine.submit(sell(1, 100, 10))
    engine.submit(buy(2, 100, 10))
    assert 100 not in engine.orderbook.asks
    assert engine.orderbook.ask_prices == []


def test_exact_fill_deletes_bid_price_key(engine):
    engine.submit(buy(1, 100, 10))
    engine.submit(sell(2, 100, 10))
    assert 100 not in engine.orderbook.bids
    assert engine.orderbook.bid_prices == []


def test_fill_keeps_price_key_while_orders_remain_at_level(engine):
    engine.submit(sell(1, 100, 5))
    engine.submit(sell(2, 100, 5))
    engine.submit(buy(3, 100, 5))
    assert resting_ids(engine.orderbook.asks, 100) == [2]
    assert engine.orderbook.best_ask() == 100
    assert_book_consistent(engine)


def test_price_level_can_be_reused_after_deletion(engine):
    engine.submit(sell(1, 100, 5))
    engine.submit(buy(2, 100, 5))
    engine.submit(sell(3, 100, 7))
    assert resting_ids(engine.orderbook.asks, 100) == [3]
    assert engine.orderbook.best_ask() == 100
    assert_book_consistent(engine)


# --- partial fills -------------------------------------------------------------

def test_incoming_smaller_than_resting_leaves_resting_remainder(engine):
    engine.submit(sell(1, 100, 10))
    trades = engine.submit(buy(2, 100, 4))
    assert trades == [Trade(2, 1, 100, 4)]
    assert engine.orderbook.asks[100][0].quantity == 6
    assert engine.orderbook.best_bid() is None
    assert_book_consistent(engine)


def test_incoming_larger_than_resting_rests_remainder_at_limit_price(engine):
    engine.submit(sell(1, 100, 4))
    trades = engine.submit(buy(2, 101, 10))
    assert trades == [Trade(2, 1, 100, 4)]
    assert engine.orderbook.best_ask() is None
    assert engine.orderbook.best_bid() == 101
    assert engine.orderbook.bids[101][0].quantity == 6
    assert_book_consistent(engine)


def test_sell_incoming_larger_than_resting_rests_remainder(engine):
    engine.submit(buy(1, 100, 4))
    trades = engine.submit(sell(2, 99, 10))
    assert trades == [Trade(1, 2, 100, 4)]
    assert engine.orderbook.best_bid() is None
    assert engine.orderbook.best_ask() == 99
    assert engine.orderbook.asks[99][0].quantity == 6
    assert_book_consistent(engine)


def test_successive_partial_fills_drain_resting_order(engine):
    engine.submit(sell(1, 100, 10))
    assert engine.submit(buy(2, 100, 3)) == [Trade(2, 1, 100, 3)]
    assert engine.submit(buy(3, 100, 3)) == [Trade(3, 1, 100, 3)]
    assert engine.submit(buy(4, 100, 4)) == [Trade(4, 1, 100, 4)]
    assert engine.orderbook.best_ask() is None
    assert_book_consistent(engine)


def test_fractional_quantities(engine):
    engine.submit(sell(1, 100, 0.5))
    trades = engine.submit(buy(2, 100, 0.25))
    assert trades == [Trade(2, 1, 100, 0.25)]
    assert engine.orderbook.asks[100][0].quantity == 0.25


# --- multi-level sweeps and price rules ---------------------------------------

def test_buy_sweeps_multiple_ask_levels_in_price_order(engine):
    engine.submit(sell(1, 102, 5))
    engine.submit(sell(2, 100, 5))
    engine.submit(sell(3, 101, 5))
    trades = engine.submit(buy(4, 102, 15))
    assert [(t.sell_order_id, t.price) for t in trades] == [(2, 100), (3, 101), (1, 102)]
    assert engine.orderbook.best_ask() is None
    assert_book_consistent(engine)


def test_sell_sweeps_multiple_bid_levels_in_price_order(engine):
    engine.submit(buy(1, 98, 5))
    engine.submit(buy(2, 100, 5))
    engine.submit(buy(3, 99, 5))
    trades = engine.submit(sell(4, 98, 15))
    assert [(t.buy_order_id, t.price) for t in trades] == [(2, 100), (3, 99), (1, 98)]
    assert engine.orderbook.best_bid() is None
    assert_book_consistent(engine)


def test_sweep_stops_at_limit_price(engine):
    engine.submit(sell(1, 100, 5))
    engine.submit(sell(2, 102, 5))
    trades = engine.submit(buy(3, 101, 10))
    assert trades == [Trade(3, 1, 100, 5)]
    assert engine.orderbook.best_ask() == 102
    assert engine.orderbook.best_bid() == 101
    assert engine.orderbook.bids[101][0].quantity == 5
    assert_book_consistent(engine)


def test_trade_executes_at_resting_price_not_aggressor_price(engine):
    engine.submit(sell(1, 100, 5))
    assert engine.submit(buy(2, 105, 5))[0].price == 100
    engine.submit(buy(3, 100, 5))
    assert engine.submit(sell(4, 95, 5))[0].price == 100


def test_price_priority_beats_time_priority(engine):
    engine.submit(sell(1, 101, 5))
    engine.submit(sell(2, 100, 5))
    trades = engine.submit(buy(3, 101, 5))
    assert trades == [Trade(3, 2, 100, 5)]
    assert resting_ids(engine.orderbook.asks, 101) == [1]


def test_best_bid_is_highest_and_best_ask_is_lowest(engine):
    for i, p in enumerate([98, 100, 99], start=1):
        engine.submit(buy(i, p, 1))
    for i, p in enumerate([103, 101, 102], start=10):
        engine.submit(sell(i, p, 1))
    assert engine.orderbook.best_bid() == 100
    assert engine.orderbook.best_ask() == 101
    assert_book_consistent(engine)


# --- FIFO ----------------------------------------------------------------------

def test_fifo_at_identical_ask_price(engine):
    engine.submit(sell(1, 100, 5))
    engine.submit(sell(2, 100, 5))
    engine.submit(sell(3, 100, 5))
    trades = engine.submit(buy(4, 100, 10))
    assert [t.sell_order_id for t in trades] == [1, 2]
    assert resting_ids(engine.orderbook.asks, 100) == [3]
    assert_book_consistent(engine)


def test_fifo_at_identical_bid_price(engine):
    engine.submit(buy(1, 100, 5))
    engine.submit(buy(2, 100, 5))
    engine.submit(buy(3, 100, 5))
    trades = engine.submit(sell(4, 100, 10))
    assert [t.buy_order_id for t in trades] == [1, 2]
    assert resting_ids(engine.orderbook.bids, 100) == [3]
    assert_book_consistent(engine)


def test_partially_filled_order_keeps_queue_priority(engine):
    engine.submit(sell(1, 100, 10))
    engine.submit(sell(2, 100, 10))
    engine.submit(buy(3, 100, 4))
    trades = engine.submit(buy(4, 100, 8))
    assert [(t.sell_order_id, t.quantity) for t in trades] == [(1, 6), (2, 2)]
    assert_book_consistent(engine)


def test_fifo_survives_cancel_in_the_middle(engine):
    for i in (1, 2, 3):
        engine.submit(sell(i, 100, 5))
    assert engine.cancel(2) is True
    trades = engine.submit(buy(4, 100, 10))
    assert [t.sell_order_id for t in trades] == [1, 3]
    assert_book_consistent(engine)


# --- cancel --------------------------------------------------------------------

def test_cancel_resting_bid(engine):
    engine.submit(buy(1, 100, 5))
    assert engine.cancel(1) is True
    assert engine.orderbook.best_bid() is None
    assert 100 not in engine.orderbook.bids
    assert engine.orderbook.bid_prices == []


def test_cancel_resting_ask(engine):
    engine.submit(sell(1, 100, 5))
    assert engine.cancel(1) is True
    assert engine.orderbook.best_ask() is None
    assert 100 not in engine.orderbook.asks
    assert engine.orderbook.ask_prices == []


def test_cancel_nonexistent_order_returns_false(engine):
    assert engine.cancel(999) is False


def test_cancel_nonexistent_order_leaves_book_untouched(engine):
    engine.submit(buy(1, 99, 5))
    engine.submit(sell(2, 101, 5))
    assert engine.cancel(999) is False
    assert engine.orderbook.best_bid() == 99
    assert engine.orderbook.best_ask() == 101
    assert_book_consistent(engine)


def test_cancel_twice_returns_false_the_second_time(engine):
    engine.submit(buy(1, 100, 5))
    assert engine.cancel(1) is True
    assert engine.cancel(1) is False


def test_cancel_already_filled_order_returns_false(engine):
    engine.submit(sell(1, 100, 5))
    engine.submit(buy(2, 100, 5))
    assert engine.cancel(1) is False
    assert engine.cancel(2) is False
    assert_book_consistent(engine)


def test_cancel_one_of_many_at_level_keeps_level(engine):
    engine.submit(buy(1, 100, 5))
    engine.submit(buy(2, 100, 5))
    assert engine.cancel(1) is True
    assert resting_ids(engine.orderbook.bids, 100) == [2]
    assert engine.orderbook.best_bid() == 100
    assert_book_consistent(engine)


def test_cancel_best_price_promotes_next_level(engine):
    engine.submit(buy(1, 100, 5))
    engine.submit(buy(2, 99, 5))
    engine.submit(sell(3, 102, 5))
    engine.submit(sell(4, 103, 5))
    engine.cancel(1)
    engine.cancel(3)
    assert engine.orderbook.best_bid() == 99
    assert engine.orderbook.best_ask() == 103
    assert_book_consistent(engine)


def test_cancel_partially_filled_order(engine):
    engine.submit(sell(1, 100, 10))
    engine.submit(buy(2, 100, 4))
    assert engine.cancel(1) is True
    assert engine.orderbook.best_ask() is None
    assert engine.submit(buy(3, 100, 6)) == []
    assert_book_consistent(engine)


def test_cancelled_order_is_not_matched(engine):
    engine.submit(sell(1, 100, 5))
    engine.cancel(1)
    assert engine.submit(buy(2, 100, 5)) == []
    assert engine.orderbook.best_bid() == 100
    assert_book_consistent(engine)


def test_cancel_does_not_touch_other_side_with_same_price(engine):
    engine.submit(buy(1, 100, 5))
    engine.submit(sell(2, 101, 5))
    engine.cancel(2)
    assert engine.orderbook.best_bid() == 100
    assert resting_ids(engine.orderbook.bids, 100) == [1]
    assert_book_consistent(engine)


# --- caller-visible behavior ---------------------------------------------------

def test_submit_mutates_incoming_order_quantity_to_remainder(engine):
    engine.submit(sell(1, 100, 4))
    incoming = buy(2, 100, 10)
    engine.submit(incoming)
    assert incoming.quantity == 6


# --- randomized invariants -----------------------------------------------------

def resting_orders(engine):
    book = engine.orderbook
    return [o for levels in (book.bids, book.asks) for q in levels.values() for o in q]


@pytest.mark.parametrize("seed", range(20))
def test_random_operations_preserve_invariants(seed):
    rng = random.Random(seed)
    engine = MatchingEngine()
    submitted_qty = traded_qty = cancelled_qty = 0

    for order_id in range(1, 301):
        resting = resting_orders(engine)
        if resting and rng.random() < 0.25:
            victim = rng.choice(resting)
            cancelled_qty += victim.quantity
            assert engine.cancel(victim.order_id) is True
        else:
            make = rng.choice([buy, sell])
            order = make(order_id, rng.randint(95, 105), rng.randint(1, 10))
            submitted_qty += order.quantity
            traded_qty += sum(t.quantity for t in engine.submit(order))

        assert_book_consistent(engine)

    resting_qty = sum(o.quantity for o in resting_orders(engine))
    # each trade consumes quantity from both a buy and a sell
    assert submitted_qty == 2 * traded_qty + resting_qty + cancelled_qty
