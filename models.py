from enum import Enum
from dataclasses import dataclass

class Side(Enum):
    BUY = "BUY"
    SELL = "SELL"
    
@dataclass
class Order:
    order_id: int
    side: Side
    price: float
    quantity: float

@dataclass(frozen=True) # frozen because Trades are immutable historical events
class Trade:
    buy_order_id: int
    sell_order_id: int
    price: float
    quantity: float