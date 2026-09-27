from engine import MatchingEngine, Order, Side

if __name__ == "__main__":
    engine = MatchingEngine()
    trades = []
    
    order1 = Order(order_id=1, side=Side.BUY, price=100.0, quantity=10)
    order2 = Order(order_id=2, side=Side.SELL, price=99.0, quantity=5)
    order3 = Order(order_id=3, side=Side.SELL, price=101.0, quantity=5)
    
    trades +=engine.submit(order1)
    trades += engine.submit(order2)
    trades += engine.submit(order3)
    
    for trade in trades:
        print(f"Trade executed: Buy Order ID {trade.buy_order_id}, Sell Order ID {trade.sell_order_id}, Price {trade.price}, Quantity {trade.quantity}")