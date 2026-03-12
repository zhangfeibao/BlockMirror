from ramgs.testkit import McuConnection


class IceMaker:
    """制冰机控制类，通过MCU串口连接读写设备参数。"""

    def __init__(self) -> None:
        self.mcu: McuConnection = McuConnection()
        self.mcu.open()

    # ==================== 输出控制 (output_cache) ====================

    def set_compressor(self, on_off: bool) -> None:
        """压缩机使能控制"""
        self.mcu.set("s_context.output_cache.fg_compressor_enable", on_off)
        print(f"设置压缩机使能: {on_off}")

    def set_fan(self, on_off: bool) -> None:
        """散热风机使能控制"""
        self.mcu.set("s_context.output_cache.fg_fan_enable", on_off)
        print(f"设置散热风机使能: {on_off}")

    def set_refrigerant_valve(self, on_off: bool) -> None:
        """冷媒阀控制"""
        self.mcu.set("s_context.output_cache.fg_refrigerant_valve", on_off)
        print(f"设置冷媒阀: {on_off}")

    def set_loop_pump(self, on_off: bool) -> None:
        """水盒循环水泵控制"""
        self.mcu.set("s_context.output_cache.fg_water_loop_pump", on_off)
        print(f"设置循环水泵: {on_off}")

    def set_coldwater_out_pump(self, on_off: bool) -> None:
        """出冷水水泵控制"""
        self.mcu.set("s_context.output_cache.fg_coldwater_out_pump", on_off)
        print(f"设置出冷水水泵: {on_off}")

    def set_ice_outlet_valve(self, on_off: bool) -> None:
        """出冰电磁阀控制"""
        self.mcu.set("s_context.output_cache.fg_ice_outlet_valve", on_off)
        print(f"设置出冰电磁阀: {on_off}")

    def set_drain_valve(self, on_off: bool) -> None:
        """排水阀控制"""
        self.mcu.set("s_context.output_cache.fg_drain_val", on_off)
        print(f"设置排水阀: {on_off}")

    def set_drain_pump(self, on_off: bool) -> None:
        """排水泵控制"""
        self.mcu.set("s_context.output_cache.fg_drainPump", on_off)
        print(f"设置排水泵: {on_off}")

    # ==================== 输入开关设置 (input_cache) ====================

    def set_cool_func_switch(self, on_off: bool) -> None:
        """制冷功能开关状态"""
        self.mcu.set("s_context.input_cache.fg_cool_func_switch", on_off)
        print(f"设置制冷功能开关: {on_off}")

    def set_ice_func_switch(self, on_off: bool) -> None:
        """制冰功能开关状态"""
        self.mcu.set("s_context.input_cache.fg_ice_func_switch", on_off)
        print(f"设置制冰功能开关: {on_off}")

    # ==================== 时间参数设置 (status_cache / config) ====================

    def set_ice_making_timer(self, time_msec: int) -> None:
        """制冰运行时间"""
        self.mcu.set("s_context.status_cache.u16ice_making_timer_msec", time_msec)
        print(f"设置制冰运行时间: {time_msec}")

    def set_harvesting_timer(self, time_msec: int) -> None:
        """脱冰运行时间"""
        self.mcu.set("s_context.status_cache.u16harverting_timer_msec", time_msec)
        print(f"设置脱冰运行时间: {time_msec}")

    def set_target_ice_making_time(self, time_msec: int) -> None:
        """目标制冰时间 (x100ms)"""
        self.mcu.set("s_context.config.u16target_ice_making_time_msec", time_msec)
        print(f"设置目标制冰时间: {time_msec}")

    def set_target_ice_harvest_time(self, time_msec: int) -> None:
        """目标脱冰时间 (x100ms)"""
        self.mcu.set("s_context.config.u16target_ice_harvest_time_msec", time_msec)
        print(f"设置目标脱冰时间: {time_msec}")

    # ==================== 特殊控制 ====================

    def stir_motor_once(self) -> None:
        """控制同步电机立即搅拌一次"""
        self.mcu.set("s_context.u16iceFullCycStirTimeCnt", 5 * 60 * 10)
        self.mcu.set("s_context.u16iceMakeCycStirTimeCnt", 8 * 60 * 10)
        print("触发同步电机搅拌一次")

    # ==================== 获取接口 (input_cache) ====================

    def get_cool_func_switch(self) -> bool:
        """制冷功能开关状态"""
        val = self.mcu.get("s_context.input_cache.fg_cool_func_switch")
        print(f"制冷功能开关: {val}")
        return val

    def get_ice_func_switch(self) -> bool:
        """制冰功能开关状态"""
        val = self.mcu.get("s_context.input_cache.fg_ice_func_switch")
        print(f"制冰功能开关: {val}")
        return val

    def get_ice_out_switch(self) -> bool:
        """出冰开关状态"""
        val = self.mcu.get("s_context.input_cache.fg_ice_out_switch")
        print(f"出冰开关: {val}")
        return val

    def get_ice_type_switch(self) -> bool:
        """冰块类型: False=慢冰, True=快冰"""
        val = self.mcu.get("s_context.input_cache.fg_ice_type_switch")
        print(f"冰块类型: {val}")
        return val

    def get_cool_water_box_high_switch(self) -> bool:
        """冷水箱高水位开关"""
        val = self.mcu.get("s_context.input_cache.fg_coolWaterBoxHigh_switch")
        print(f"冷水箱高水位: {val}")
        return val

    def get_ambient_temp(self) -> int:
        """环境温度值 (C)"""
        val = self.mcu.get("s_context.input_cache.u8ambient_temp")
        print(f"环境温度: {val}")
        return val

    def get_cool_water_temp(self) -> int:
        """冷水温度值 (C)"""
        val = self.mcu.get("s_context.input_cache.u8cool_water_temp")
        print(f"冷水温度: {val}")
        return val

    def get_evaporator_temp(self) -> int:
        """蒸发器温度值 (C)"""
        val = self.mcu.get("s_context.input_cache.i8evaporator_temp")
        print(f"蒸发器温度: {val}")
        return val

    def get_ice_full_state(self) -> bool:
        """满冰检测信号"""
        val = self.mcu.get("s_context.input_cache.fg_ice_full_detected")
        print(f"满冰检测: {val}")
        return val

    # ==================== 获取接口 (status_cache / config) ====================

    def get_ice_making_timer(self) -> int:
        """制冰运行时间"""
        val = self.mcu.get("s_context.status_cache.u16ice_making_timer_msec")
        print(f"制冰运行时间: {val}")
        return val

    def get_harvesting_timer(self) -> int:
        """脱冰运行时间"""
        val = self.mcu.get("s_context.status_cache.u16harverting_timer_msec")
        print(f"脱冰运行时间: {val}")
        return val

    def get_target_ice_making_time(self) -> int:
        """目标制冰时间 (x100ms)"""
        val = self.mcu.get("s_context.config.u16target_ice_making_time_msec")
        print(f"目标制冰时间: {val}")
        return val

    def get_target_ice_harvest_time(self) -> int:
        """目标脱冰时间 (x100ms)"""
        val = self.mcu.get("s_context.config.u16target_ice_harvest_time_msec")
        print(f"目标脱冰时间: {val}")
        return val


# 模块级单例
ice: IceMaker = IceMaker()


