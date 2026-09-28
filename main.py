from models import Side
from engine import MatchingEngine

if __name__ == "__main__":
    engine = MatchingEngine()

    # The assignment's own worked example: four resting sells, then a buy
    # that sweeps 101 (two orders, FIFO), takes part of 102, and rests the
    # remainder as the new best bid; 103 is never touched.
    engine.place_order(Side.SELL, 101, 5)
    engine.place_order(Side.SELL, 101, 3)
    engine.place_order(Side.SELL, 102, 2)
    engine.place_order(Side.SELL, 103, 4)

    order_id, trades = engine.place_order(Side.BUY, 102, 12)

    for trade in trades:
        print(f"Trade: buy #{trade.buy_order_id} <-> sell #{trade.sell_order_id}, "
              f"{trade.quantity} @ {trade.price}")

    print(f"Order #{order_id} rests: best_bid={engine.best_bid()}, best_ask={engine.best_ask()}")
    print(f"Top levels: {engine.top_levels(5)}")
    print(engine.orderbook)
    print(f"cancel(#{order_id}) -> {engine.cancel(order_id)}")
    print(f"trade_history: {engine.trade_history()}")
