import heapq
from models import Order, Side, Trade

class Node:
    def __init__(self, order):
        self.order = order
        self.prev = None
        self.next = None
    
    def detach(self):
        self.prev.next = self.next
        self.next.prev = self.prev
        self.prev = None
        self.next = None

class PriceLevel:
    def __init__(self):
        self.head = Node(None)  # sentinel node
        self.tail = Node(None)  # sentinel node
        self.head.next = self.tail
        self.tail.prev = self.head
        
    def __iter__(self):
        node = self.head.next
        while node is not self.tail:
            yield node.order
            node = node.next
        
    def add(self, new_node):
        new_node.next = self.tail
        new_node.prev = self.tail.prev
        self.tail.prev.next = new_node
        self.tail.prev = new_node

class OrderBook:
    def __init__(self):
        # dictionaries to hold orders at each price level
        self.bids = {} # price -> PriceLevel of orders
        self.asks = {} # price -> PriceLevel of orders
        
        # heaps with prices
        self.bid_prices = [] # max-heap for bids
        self.ask_prices = [] # min-heap for asks
        
        self.order_map = {} # order_id -> Node

    def best_bid(self):
        while self.bid_prices and -self.bid_prices[0] not in self.bids:
            heapq.heappop(self.bid_prices)
        return -self.bid_prices[0] if self.bid_prices else None
    
    def best_ask(self):
        while self.ask_prices and self.ask_prices[0] not in self.asks:
            heapq.heappop(self.ask_prices)
        return self.ask_prices[0] if self.ask_prices else None
    
    def add(self, order):
        node = Node(order)
        self.order_map[order.order_id] = node
        
        if order.side == Side.BUY:
            is_new_level = order.price not in self.bids
            self.bids.setdefault(order.price, PriceLevel()).add(node)
            if is_new_level:
                heapq.heappush(self.bid_prices, -order.price) # max-heap
        else:
            is_new_level = order.price not in self.asks
            self.asks.setdefault(order.price, PriceLevel()).add(node)
            if is_new_level:
                heapq.heappush(self.ask_prices, order.price) # min-heap

    def remove(self, order_id):
        if order_id in self.order_map:
            node = self.order_map.pop(order_id)
            price, side = node.order.price, node.order.side
            node.detach()
            
            if side == Side.BUY and self.bids[price].head.next == self.bids[price].tail:
                del self.bids[price]
                
            elif side == Side.SELL and self.asks[price].head.next == self.asks[price].tail:
                del self.asks[price]
            
            return True
                        
        return False # order_id not found
    
    def top_levels(self, n):
        """Top n price levels per side as (price, total_quantity), best price first."""

        def depth(levels, prices):
            return [(price, sum(o.quantity for o in levels[price])) for price in prices]

        return (depth(self.bids, heapq.nlargest(n, self.bids)),
            depth(self.asks, heapq.nsmallest(n, self.asks)))

    def __repr__(self):
        bids, asks = self.top_levels(5)
        if not bids and not asks:
            return "<empty book>"
        lines = [f"{price:>8}  ask {qty}" for price, qty in reversed(asks)]
        lines.append("-" * 20)
        lines += [f"{price:>8}  bid {qty}" for price, qty in bids]
        return "\n".join(lines)


class MatchingEngine:

    def __init__(self):
        self.orderbook = OrderBook()
        self._next_order_id = 1
        self.trade_log = [] # every Trade ever produced, in execution order

    def place_order(self, side, price, quantity) -> tuple[int, list[Trade]]:
        """Accepts raw order parameters, assigns an id, and returns (order_id, trades)."""

        order_id = self._next_order_id
        self._next_order_id += 1

        order = Order(order_id=order_id, side=side, price=price, quantity=quantity)
        trades = self.submit(order)

        return order_id, trades

    def submit(self, order) -> list[Trade]:
        if order.price < 0 or order.quantity < 0:
            raise ValueError(f"order price and quantity must be non-negative "
                              f"(got price={order.price}, quantity={order.quantity})")

        trades = self._match(order)

        if order.quantity > 0: # if there is remaining quantity, add to orderbook
            self.orderbook.add(order)

        self.trade_log.extend(trades)
        return trades

    def trade_history(self) -> list[Trade]:
        """Every trade this engine has produced, in execution order."""
        return list(self.trade_log)

    def _match(self, order) -> list[Trade]:
        trades = []
        is_buy = order.side == Side.BUY
        book = self.orderbook.asks if is_buy else self.orderbook.bids
        best_price = self.orderbook.best_ask if is_buy else self.orderbook.best_bid
        
        while order.quantity > 0 and best_price() is not None:
            resting_price = best_price()
            crossed = order.price >= resting_price if is_buy else order.price <= resting_price
            
            if not crossed:
                break
            
            level = book[resting_price] # PriceLevel at key resting_price
            resting_node = level.head.next # FIFO
            resting_order = resting_node.order
            
            trade_quantity = min(order.quantity, resting_order.quantity)
            
            if is_buy:
                trades.append(Trade(buy_order_id=order.order_id, sell_order_id=resting_order.order_id, 
                                    price=resting_price, quantity=trade_quantity))
            else:
                trades.append(Trade(buy_order_id=resting_order.order_id, sell_order_id=order.order_id, 
                                    price=resting_price, quantity=trade_quantity))
            
            order.quantity -= trade_quantity
            resting_order.quantity -= trade_quantity
            
            if resting_order.quantity == 0:
                resting_node.detach() # detach the order from the LinikedList
                del self.orderbook.order_map[resting_order.order_id]
                
                if level.head.next is level.tail:
                    del book[resting_price] # level is empty
        
        return trades
    
    def cancel(self, order_id) -> bool:
        return self.orderbook.remove(order_id)

    def best_bid(self):
        return self.orderbook.best_bid()

    def best_ask(self):
        return self.orderbook.best_ask()

    def top_levels(self, n):
        return self.orderbook.top_levels(n)