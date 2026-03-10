from ramgs.testkit import McuConnection


class IceMaker:
    """制冰机控制类，通过MCU串口连接读写设备参数。"""

    def __init__(self) -> None:
        # 创建MCU连接并打开串口
        self.mcu: McuConnection = McuConnection()
        self.mcu.open()

    def get_temp_down(self) -> int:
        """读取MCU定时器1秒计数值。"""
        value: int = self.mcu.get("timerObj.timer_1sec_count")
        print(f"获取timerObj.timer_1sec_count值：{value}")
        return value

    def set_temp_down(self, t: int) -> None:
        """设置MCU定时器1秒计数值。

        Args:
            t: 要写入的计数值
        """
        self.mcu.set("timerObj.timer_1sec_count", t)
        print(f"设置timerObj.timer_1sec_count值：{t}")


# 模块级单例，其他模块通过 from ice_maker.ice import ice 使用
ice: IceMaker = IceMaker()


