"""
制冰机制冰过程控制程序
- 使用 ice.py 提供的模块级单例 `ice` 与设备交互
- 基于简单状态机实现：待机 -> 制冰 -> 脱冰 -> 循环/结束
- 具备水位检测、满冰检测、超时保护与异常安全退出
"""

import time
from typing import Optional

# 引入 ice 单例
from ice import ice


# ========================== 基础控制工具函数 ==========================

def safe_shutdown() -> None:
    """安全停机：关闭所有可能的执行器"""
    try:
        ice.set_ice_outlet_valve(False)
        ice.set_coldwater_out_pump(False)

        ice.set_drain_valve(False)
        ice.set_drain_pump(False)

        ice.set_loop_pump(False)
        ice.set_refrigerant_valve(False)

        ice.set_fan(False)
        ice.set_compressor(False)
        print("[安全] 已关闭全部输出")
    except Exception as e:
        print(f"[安全] 关闭输出时发生异常: {e}")


def wait_for_water_high(timeout_s: int = 300, poll_s: float = 1.0) -> bool:
    """
    等待冷水箱高水位开关为 True
    - timeout_s: 超时时间（秒）
    - 返回 True 表示水位达到，False 表示超时未达
    """
    t0 = time.time()
    while time.time() - t0 < timeout_s:
        try:
            if ice.get_cool_water_box_high_switch():
                print("[水位] 冷水箱高水位已到位")
                return True
        except Exception as e:
            print(f"[水位] 读取水位异常: {e}")
        time.sleep(poll_s)
    print("[水位] 等待水位超时")
    return False


def poll_env():
    """读取并打印关键环境参数，便于调试观察"""
    try:
        ambient = ice.get_ambient_temp()
        cool_water = ice.get_cool_water_temp()
        evap = ice.get_evaporator_temp()
        full = ice.get_ice_full_state()
        print(f"[环境] 环境={ambient}C 冷水={cool_water}C 蒸发器={evap}C 满冰={full}")
    except Exception as e:
        print(f"[环境] 读取环境参数异常: {e}")


# ========================== 状态阶段实现 ==========================

def stage_prepare() -> bool:
    """
    准备阶段：
    - 确保排水阀/泵关闭
    - 等待冷水箱水位到位
    - 返回 True 表示可以进入制冰
    """
    print("[阶段] 准备阶段")
    ice.set_drain_valve(False)
    ice.set_drain_pump(False)

    # 可选：读取制冰功能开关决定是否继续
    try:
        if not ice.get_ice_func_switch():
            print("[阶段] 制冰功能开关为关，退出")
            return False
    except Exception:
        # 若读取失败，默认继续
        pass

    # 等待水位
    if not wait_for_water_high(timeout_s=300):
        print("[阶段] 水位未到位，放弃此次制冰")
        return False
    return True


def stage_make_ice(duration_s: int,
                   poll_s: float = 2.0,
                   stop_on_full: bool = True) -> str:
    """
    制冰阶段：
    - 打开：循环水泵、冷媒阀、散热风机、压缩机
    - 在 duration_s 限时内循环监测；可因满冰/水位丢失/开关关闭提前退出
    - 返回 "done" 正常完成；"full" 满冰终止；"abort" 其他原因中止
    """
    print("[阶段] 制冰阶段开始")
    # 打开制冷相关执行器
    ice.set_loop_pump(True)
    ice.set_refrigerant_valve(True)
    ice.set_fan(True)
    ice.set_compressor(True)

    # 将目标时间写入设备配置（仅用于记录/观察）
    try:
        ice.set_target_ice_making_time(int(duration_s * 1000))
    except Exception:
        pass

    t0 = time.time()
    last_poll = 0.0
    try:
        while time.time() - t0 < duration_s:
            now = time.time()
            if now - last_poll >= poll_s:
                poll_env()
                last_poll = now

                # 满冰检测
                if stop_on_full and ice.get_ice_full_state():
                    print("[阶段] 检测到满冰，提前结束制冰阶段")
                    return "full"

                # 水位丢失，暂停压缩机与风机，等待水位恢复
                if not ice.get_cool_water_box_high_switch():
                    print("[阶段] 检测到水位低，暂停制冷等待补水")
                    ice.set_compressor(False)
                    ice.set_fan(False)
                    if not wait_for_water_high(timeout_s=180):
                        print("[阶段] 水位长时间未恢复，放弃此次制冰")
                        return "abort"
                    # 恢复制冷
                    ice.set_fan(True)
                    ice.set_compressor(True)

                # 可选：制冰功能开关变为关闭则中止
                try:
                    if not ice.get_ice_func_switch():
                        print("[阶段] 制冰功能被关闭，中止当前制冰阶段")
                        return "abort"
                except Exception:
                    pass

            time.sleep(0.2)

        print("[阶段] 制冰阶段时间到")
        return "done"
    finally:
        # 制冰阶段结束先关压缩机和风机，防止继续冷却
        ice.set_compressor(False)
        ice.set_fan(False)


def stage_harvest(duration_s: int,
                  assist_stir: bool = True) -> None:
    """
    脱冰阶段：
    - 关闭压缩相关，打开出冰电磁阀，启动出冷水泵协助脱冰
    - 可触发一次搅拌电机协助推冰
    """
    print("[阶段] 脱冰阶段开始")
    # 冗余关闭（若上个阶段已关闭不影响）
    ice.set_compressor(False)
    ice.set_fan(False)

    # 开启帮助脱冰与出冰的执行器
    ice.set_ice_outlet_valve(True)
    ice.set_coldwater_out_pump(True)

    # 写入目标脱冰时间（仅用于记录/观察）
    try:
        ice.set_target_ice_harvest_time(int(duration_s * 1000))
    except Exception:
        pass

    if assist_stir:
        try:
            ice.stir_motor_once()
        except Exception as e:
            print(f"[阶段] 触发搅拌失败: {e}")

    t0 = time.time()
    while time.time() - t0 < duration_s:
        # 可在脱冰过程中打印一次环境信息
        if int(time.time() - t0) % 3 == 0:
            poll_env()
        time.sleep(0.5)

    # 关闭出冰相关
    ice.set_coldwater_out_pump(False)
    ice.set_ice_outlet_valve(False)
    print("[阶段] 脱冰阶段结束")


# ========================== 主流程（循环） ==========================

def run_ice_process(max_cycles: Optional[int] = None,
                    stop_on_full: bool = True,
                    fast_slow_auto: bool = True) -> None:
    """
    运行制冰机流程（可循环多次）
    - max_cycles: 最大制冰+脱冰循环次数；None 表示无限循环，直到开关关闭或满冰停止
    - stop_on_full: 检测到满冰后停止后续循环
    - fast_slow_auto: 根据冰块类型开关自动调整时长（快冰/慢冰）
    """
    print("========== 制冰流程启动 ==========")
    cycles_done = 0

    # 建议在流程启动时确保所有输出为关闭态
    safe_shutdown()

    try:
        while True:
            # 可选：按功能开关决定是否继续
            try:
                if not ice.get_ice_func_switch():
                    print("[主循环] 制冰功能开关为关，等待用户开启...")
                    time.sleep(2.0)
                    continue
            except Exception:
                # 若读取失败，继续执行
                pass

            # 动态选择快冰/慢冰时长
            make_time_s = 12 * 60  # 默认慢冰 12 分钟
            harvest_time_s = 75     # 脱冰默认 75 秒
            try:
                fast = ice.get_ice_type_switch()  # False=慢冰, True=快冰
                if fast_slow_auto and fast:
                    make_time_s = 9 * 60   # 快冰 9 分钟
                    harvest_time_s = 60    # 脱冰 60 秒
                else:
                    make_time_s = 12 * 60  # 慢冰 12 分钟
                    harvest_time_s = 80    # 脱冰 80 秒
            except Exception:
                pass

            # 准备阶段
            if not stage_prepare():
                # 若准备失败，稍后重试
                time.sleep(3.0)
                continue

            # 制冰阶段
            result = stage_make_ice(duration_s=make_time_s,
                                    poll_s=2.0,
                                    stop_on_full=stop_on_full)

            if result == "full":
                print("[主循环] 满冰结束，进入一次脱冰以确保出冰通畅")
                stage_harvest(duration_s=harvest_time_s, assist_stir=True)
                print("[主循环] 满冰已处理，流程停止")
                break
            elif result == "abort":
                print("[主循环] 本轮制冰中止，清理后等待重试")
                safe_shutdown()
                time.sleep(3.0)
                continue
            else:
                print("[主循环] 制冰时间到，进入脱冰阶段")
                stage_harvest(duration_s=harvest_time_s, assist_stir=True)

            cycles_done += 1
            print(f"[主循环] 已完成循环次数: {cycles_done}")

            # 达到最大循环次数则退出
            if max_cycles is not None and cycles_done >= max_cycles:
                print("[主循环] 达到设定循环次数，流程结束")
                break

            # 短暂休息，进入下一轮
            time.sleep(2.0)

    except KeyboardInterrupt:
        print("[主循环] 收到用户中断，执行安全停机")
    except Exception as e:
        print(f"[主循环] 流程发生异常: {e}")
    finally:
        safe_shutdown()
        print("========== 制冰流程结束 ==========")


# ========================== 可执行入口 ==========================

if __name__ == "__main__":
    # 示例：无限循环，检测到满冰后停止；自动根据快冰/慢冰开关调整时间
    run_ice_process(max_cycles=None, stop_on_full=True, fast_slow_auto=True)