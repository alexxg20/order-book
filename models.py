from enum import Enum
from dataclasses import dataclass

class Side(Enum):
    BUY = "BUY"
    SELL = "SELL"
    
@dataclass
class Order:
    order_id: int
    side: Side
    price: int
    quantity: float

@dataclass(frozen=True) # frozen because Trades are immutable historical events
class Trade:
    buy_order_id: int
    sell_order_id: int
    price: int
    quantity: float