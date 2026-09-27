#!/usr/bin/env python3
"""End-to-end throughput generator for MatchingEngine.

Submits a stream of random orders (with a configurable share of cancels
against currently-resting orders) and reports ops/sec. A fixed --seed keeps
runs comparable across changes to engine.py.

    python3 load_test.py --ops 200000
    python3 load_test.py --ops 200000 --profile   # cProfile summary instead
"""
import argparse
import cProfile
import pstats
import random
import sys
import time

from engine import MatchingEngine
from models import Order, Side


def run(n_ops: int, seed: int, cancel_prob: float, price_range: int, max_qty: int) -> MatchingEngine:
    rng = random.Random(seed)
    engine = MatchingEngine()
    resting_ids = []  # ids currently resting on the book, so cancels hit real orders
    next_id = 1

    for _ in range(n_ops):
        if resting_ids and rng.random() < cancel_prob:
            order_id = resting_ids.pop(rng.randrange(len(resting_ids)))
            engine.cancel(order_id)
            continue

        side = Side.BUY if rng.random() < 0.5 else Side.SELL
        price = rng.randint(100, 100 + price_range)
        order = Order(order_id=next_id, side=side, price=price, quantity=rng.randint(1, max_qty))
        engine.submit(order)
        if order.quantity > 0:
            resting_ids.append(next_id)
        next_id += 1

    return engine


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--ops", type=int, default=200_000, help="number of operations to submit")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--cancel-prob", type=float, default=0.2, help="fraction of ops that are cancels")
    parser.add_argument("--price-range", type=int, default=500, help="width of the price range above 100")
    parser.add_argument("--max-qty", type=int, default=10)
    parser.add_argument("--profile", action="store_true", help="print a cProfile summary instead of just the throughput line")
    args = parser.parse_args()

    profiler = cProfile.Profile() if args.profile else None
    if profiler:
        profiler.enable()

    start = time.perf_counter()
    run(args.ops, args.seed, args.cancel_prob, args.price_range, args.max_qty)
    elapsed = time.perf_counter() - start

    if profiler:
        profiler.disable()
        pstats.Stats(profiler, stream=sys.stdout).sort_stats("cumulative").print_stats(20)

    print(f"{args.ops} ops in {elapsed:.3f}s -> {args.ops / elapsed:,.0f} ops/sec (seed={args.seed}, cancel_prob={args.cancel_prob})")


if __name__ == "__main__":
    main()
