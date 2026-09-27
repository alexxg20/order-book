from collections import defaultdict, deque
import heapq
from models import Order, Side, Trade

class OrderBook:
    def __init__(self):
        # dictionaries to hold orders at each price level
        self.bids = {} # price -> deque of orders
        self.asks = {} # price -> deque of orders
        
        # heaps with prices
        self.bid_prices = [] # max-heap for bids
        self.ask_prices = [] # min-heap for asks

    def best_bid(self): # O(1)
        return -self.bid_prices[0] if self.bids else None
    
    def best_ask(self): # O(1)
        return self.ask_prices[0] if self.asks else None
    
    def add(self, order): # O(log n)
        if order.side == Side.BUY:
            self.bids.setdefault(order.price, deque()).append(order)
            if -order.price not in self.bid_prices:
                heapq.heappush(self.bid_prices, -order.price) # max-heap
        else:
            self.asks.setdefault(order.price, deque()).append(order)
            if order.price not in self.ask_prices:
                heapq.heappush(self.ask_prices, order.price) # min-heap

    def remove(self, order_id): # O(n)
        # search in bids
        for price, orders in self.bids.items():
            for order in orders:
                if order.order_id == order_id:
                    orders.remove(order)
                    if not orders:
                        del self.bids[price]
                        self.bid_prices.remove(-price)
                        heapq.heapify(self.bid_prices)
                    return True
        
        # search in asks if not found in bids 
        for price, orders in self.asks.items():
            for order in orders:
                if order.order_id == order_id:
                    orders.remove(order)
                    if not orders:
                        del self.asks[price]
                        self.ask_prices.remove(price)
                        heapq.heapify(self.ask_prices)
                    return True
        
        return False # order_id not found

class MatchingEngine:
    
    def __init__(self):
        self.orderbook = OrderBook()

    def submit(self, order) -> list[Trade]:
        trades = self._match(order)
        
        if order.quantity > 0: # if there is remaining quantity, add to orderbook
            self.orderbook.add(order)
        
        return trades

    def _match(self, order) -> list[Trade]:
        trades = []
        
        if order.side == Side.BUY:
            while order.quantity > 0 and self.orderbook.best_ask() is not None and order.price >= self.orderbook.best_ask():
                best_ask_price = self.orderbook.best_ask()
                best_ask_orders = self.orderbook.asks[best_ask_price]
                best_ask_order = best_ask_orders[0] # FIFO
                
                trade_quantity = min(order.quantity, best_ask_order.quantity)
                trades.append(
                    Trade(buy_order_id=order.order_id, sell_order_id=best_ask_order.order_id, price=best_ask_price, quantity=trade_quantity)
                )
                
                order.quantity -= trade_quantity
                best_ask_order.quantity -= trade_quantity
                
                if best_ask_order.quantity == 0:
                    best_ask_orders.popleft() # remove the order from the deque
                    if not best_ask_orders: # if no more orders at this price level
                        del self.orderbook.asks[best_ask_price]
                        self.orderbook.ask_prices.remove(best_ask_price)
                        heapq.heapify(self.orderbook.ask_prices)
        
        else: # SELL
            while order.quantity > 0 and self.orderbook.best_bid() is not None and order.price <= self.orderbook.best_bid():
                best_bid_price = self.orderbook.best_bid()
                best_bid_orders = self.orderbook.bids[best_bid_price]
                best_bid_order = best_bid_orders[0] # FIFO
                
                trade_quantity = min(order.quantity, best_bid_order.quantity)
                trades.append(
                    Trade(buy_order_id=best_bid_order.order_id, sell_order_id=order.order_id, price=best_bid_price, quantity=trade_quantity)
                )
                
                order.quantity -= trade_quantity
                best_bid_order.quantity -= trade_quantity
                
                if best_bid_order.quantity == 0:
                    best_bid_orders.popleft() # remove the order from the deque
                    if not best_bid_orders: # if no more orders at this price level
                        del self.orderbook.bids[best_bid_price]
                        self.orderbook.bid_prices.remove(-best_bid_price)
                        heapq.heapify(self.orderbook.bid_prices)
        
        return trades
    
    def cancel(self, order_id) -> bool:
        return self.orderbook.remove(order_id)