from vnpy.event import EventEngine
from vnpy.trader.engine import MainEngine
from vnpy.trader.ui import QtWidgets, QtCore

from ..engine import APP_NAME, RiskEngine


class RiskManager(QtWidgets.QDialog):
    """"""

    def __init__(self, main_engine: MainEngine, event_engine: EventEngine) -> None:
        """"""
        super().__init__()

        self.main_engine: MainEngine = main_engine
        self.event_engine: EventEngine = event_engine
        self.rm_engine: RiskEngine = main_engine.get_engine(APP_NAME)

        self.init_ui()

    def init_ui(self) -> None:
        """"""
        self.setWindowTitle("Trading Risk Control")

        # Create widgets
        self.active_combo: QtWidgets.QComboBox = QtWidgets.QComboBox()
        self.active_combo.addItems(["Stop", "Start"])

        self.flow_limit_spin: RiskManagerSpinBox = RiskManagerSpinBox()
        self.flow_clear_spin: RiskManagerSpinBox = RiskManagerSpinBox()
        self.size_limit_spin: RiskManagerSpinBox = RiskManagerSpinBox()
        self.trade_limit_spin: RiskManagerSpinBox = RiskManagerSpinBox()
        self.active_limit_spin: RiskManagerSpinBox = RiskManagerSpinBox()
        self.cancel_limit_spin: RiskManagerSpinBox = RiskManagerSpinBox()

        save_button: QtWidgets.QPushButton = QtWidgets.QPushButton("Save")
        save_button.clicked.connect(self.save_setting)

        # Form layout
        form: QtWidgets.QFormLayout = QtWidgets.QFormLayout()
        form.addRow("ACtivity status", self.active_combo)
        form.addRow("Order flow limit", self.flow_limit_spin)
        form.addRow("Order flow clear", self.flow_clear_spin)
        form.addRow("Order linit size", self.size_limit_spin)
        form.addRow("Total trade limit", self.trade_limit_spin)
        form.addRow("Active limit", self.active_limit_spin)
        form.addRow("Contract cancellation limit", self.cancel_limit_spin)
        form.addRow(save_button)

        self.setLayout(form)

        # Set Fix Size
        hint: QtCore.QSize = self.sizeHint()
        self.setFixedSize(int(hint.width() * 1.2), hint.height())

    def save_setting(self) -> None:
        """"""
        active_text: str = self.active_combo.currentText()
        if active_text == "Start":
            active: bool = True
        else:
            active: bool = False

        setting: dict = {
            "active": active,
            "order_flow_limit": self.flow_limit_spin.value(),
            "order_flow_clear": self.flow_clear_spin.value(),
            "order_size_limit": self.size_limit_spin.value(),
            "trade_limit": self.trade_limit_spin.value(),
            "active_order_limit": self.active_limit_spin.value(),
            "order_cancel_limit": self.cancel_limit_spin.value(),
        }

        self.rm_engine.update_setting(setting)
        self.rm_engine.save_setting()

        self.close()

    def update_setting(self) -> None:
        """"""
        setting: dict = self.rm_engine.get_setting()
        if setting["active"]:
            self.active_combo.setCurrentIndex(1)
        else:
            self.active_combo.setCurrentIndex(0)

        self.flow_limit_spin.setValue(setting["order_flow_limit"])
        self.flow_clear_spin.setValue(setting["order_flow_clear"])
        self.size_limit_spin.setValue(setting["order_size_limit"])
        self.trade_limit_spin.setValue(setting["trade_limit"])
        self.active_limit_spin.setValue(setting["active_order_limit"])
        self.cancel_limit_spin.setValue(setting["order_cancel_limit"])

    def exec(self) -> None:
        """"""
        self.update_setting()
        super().exec()


class RiskManagerSpinBox(QtWidgets.QSpinBox):
    """"""

    def __init__(self, value: int = 0) -> None:
        """"""
        super().__init__()

        self.setMinimum(0)
        self.setMaximum(1_000_000_000)
        self.setValue(value)
