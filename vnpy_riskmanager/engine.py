from collections import defaultdict
from typing import Callable, Dict, Optional

from vnpy.event import Event, EventEngine
from vnpy.trader.object import OrderData, OrderRequest, LogData, TradeData
from vnpy.trader.engine import BaseEngine, MainEngine
from vnpy.trader.event import EVENT_TRADE, EVENT_ORDER, EVENT_LOG, EVENT_TIMER
from vnpy.trader.constant import Direction, Status
from vnpy.trader.utility import load_json, save_json


APP_NAME = "RiskManager"


class RiskEngine(BaseEngine):
    """Risk Control Engine"""

    setting_filename: str = "risk_manager_setting.json"

    def __init__(self, main_engine: MainEngine, event_engine: EventEngine) -> None:
        """"""
        super().__init__(main_engine, event_engine, APP_NAME)

        self.active: bool = False

        self.order_flow_count: int = 0
        self.order_flow_limit: int = 50

        self.order_flow_clear: int = 1
        self.order_flow_timer: int = 0

        self.order_size_limit: int = 100

        self.trade_count: int = 0
        self.trade_limit: int = 1000

        self.order_cancel_limit: int = 500
        self.order_cancel_counts: Dict[str, int] = defaultdict(int)

        self.active_order_limit: int = 50

        self.active_order_books: Dict[str, ActiveOrderBook] = {}

        self.load_setting()
        self.register_event()
        self.patch_send_order()

    def patch_send_order(self) -> None:
        """
        Patch send order function of MainEngine.
        """
        self._send_order: Callable[
            [OrderRequest, str], str
        ] = self.main_engine.send_order
        self.main_engine.send_order = self.send_order

    def send_order(self, req: OrderRequest, gateway_name: str) -> str:
        """"""
        result: bool = self.check_risk(req, gateway_name)
        if not result:
            return ""

        return self._send_order(req, gateway_name)

    def update_setting(self, setting: dict) -> None:
        """"""
        self.active = setting["active"]
        self.order_flow_limit = setting["order_flow_limit"]
        self.order_flow_clear = setting["order_flow_clear"]
        self.order_size_limit = setting["order_size_limit"]
        self.trade_limit = setting["trade_limit"]
        self.active_order_limit = setting["active_order_limit"]
        self.order_cancel_limit = setting["order_cancel_limit"]

        if self.active:
            self.write_log("Trade Risk Control function started")
        else:
            self.write_log("Trade Risk Control function stopped")

    def get_setting(self) -> dict:
        """"""
        setting: dict = {
            "active": self.active,
            "order_flow_limit": self.order_flow_limit,
            "order_flow_clear": self.order_flow_clear,
            "order_size_limit": self.order_size_limit,
            "trade_limit": self.trade_limit,
            "active_order_limit": self.active_order_limit,
            "order_cancel_limit": self.order_cancel_limit,
        }
        return setting

    def load_setting(self) -> None:
        """"""
        setting: dict = load_json(self.setting_filename)
        if not setting:
            return

        self.update_setting(setting)

    def save_setting(self) -> None:
        """"""
        setting: dict = self.get_setting()
        save_json(self.setting_filename, setting)

    def register_event(self) -> None:
        """"""
        self.event_engine.register(EVENT_TRADE, self.process_trade_event)
        self.event_engine.register(EVENT_TIMER, self.process_timer_event)
        self.event_engine.register(EVENT_ORDER, self.process_order_event)

    def process_order_event(self, event: Event) -> None:
        """"""
        order: OrderData = event.data

        order_book: ActiveOrderBook = self.get_order_book(order.vt_symbol)
        order_book.update_order(order)

        if order.status != Status.CANCELLED:
            return
        self.order_cancel_counts[order.vt_symbol] += 1

    def process_trade_event(self, event: Event) -> None:
        """"""
        trade: TradeData = event.data
        self.trade_count += trade.volume

    def process_timer_event(self, event: Event) -> None:
        """"""
        self.order_flow_timer += 1

        if self.order_flow_timer >= self.order_flow_clear:
            self.order_flow_count = 0
            self.order_flow_timer = 0

    def write_log(self, msg: str) -> None:
        """"""
        log: LogData = LogData(msg=msg, gateway_name="RiskManager")
        event: Event = Event(type=EVENT_LOG, data=log)
        self.event_engine.put(event)

    def check_risk(self, req: OrderRequest, gateway_name: str) -> bool:
        """"""
        if not self.active:
            return True

        # Check order volume
        if req.volume <= 0:
            self.write_log("The number of shares must be greater than 0")
            return False

        if req.volume > self.order_size_limit:
            self.write_log(
                f"Number of single commissions {req.volume}, exceeded limit {self.order_size_limit}"
            )
            return False

        # Check trade volume
        if self.trade_count >= self.trade_limit:
            self.write_log(
                f"Total number of contracts traded today {self.trade_count}, exceeded limit {self.trade_limit}"
            )
            return False

        # Check flow count
        if self.order_flow_count >= self.order_flow_limit:
            self.write_log(
                f"Order flow count {self.order_flow_count}, exceeded limit every {self.order_flow_clear} seconds {self.order_flow_limit}"
            )
            return False

        # Check all active orders
        active_order_count: int = len(self.main_engine.get_all_active_orders())
        if active_order_count >= self.active_order_limit:
            self.write_log(
                f"Current active order count {active_order_count}, exceeded limit {self.active_order_limit}"
            )
            return False

        # Check order cancel counts
        order_cancel_count: int = self.order_cancel_counts.get(req.vt_symbol, 0)
        if order_cancel_count >= self.order_cancel_limit:
            self.write_log(
                f"The number of {req.vt_symbol} order cancel {order_cancel_count} for the day, exceeded the limit {self.order_cancel_limit}"
            )
            return False

        # Check order self trade
        order_book: ActiveOrderBook = self.get_order_book(req.vt_symbol)
        if req.direction == Direction.LONG:
            best_ask: float = order_book.get_best_ask()
            if best_ask and req.price >= best_ask:
                self.write_log(
                    f"The buy price {req.price} is greater than or equal to the listed minimum ask price {best_ask}, which may result in a self-transaction"
                )
                return False
        else:
            best_bid: float = order_book.get_best_bid()
            if best_bid and req.price <= best_bid:
                self.write_log(
                    f"The sell price {req.price} is less than or equal to the lowest bid price {best_bid} that has been listed, which may result in a self-transaction"
                )
                return False

        # Add flow count if pass all checks
        self.order_flow_count += 1
        return True

    def get_order_book(self, vt_symbol: str) -> "ActiveOrderBook":
        """"""
        order_book: Optional[ActiveOrderBook] = self.active_order_books.get(
            vt_symbol, None
        )
        if not order_book:
            order_book = ActiveOrderBook(vt_symbol)
            self.active_order_books[vt_symbol] = order_book
        return order_book


class ActiveOrderBook:
    """Active order book"""

    def __init__(self, vt_symbol: str) -> None:
        """"""
        self.vt_symbol: str = vt_symbol

        self.bid_prices: Dict[str, float] = {}
        self.ask_prices: Dict[str, float] = {}

    def update_order(self, order: OrderData) -> None:
        """Updating order data"""
        if order.is_active():
            if order.direction == Direction.LONG:
                self.bid_prices[order.vt_orderid] = order.price
            else:
                self.ask_prices[order.vt_orderid] = order.price
        else:
            if order.vt_orderid in self.bid_prices:
                self.bid_prices.pop(order.vt_orderid)
            elif order.vt_orderid in self.ask_prices:
                self.ask_prices.pop(order.vt_orderid)

    def get_best_bid(self) -> float:
        """Getting the highest bid"""
        if not self.bid_prices:
            return 0
        return max(self.bid_prices.values())

    def get_best_ask(self) -> float:
        """Get the lowest ask price"""
        if not self.ask_prices:
            return 0
        return min(self.ask_prices.values())
