from ramgs.testkit import McuConnection

#进入with语句，自动连接串口
with McuConnection() as mcu:
    # 输出链接信息
    print(mcu.port_name)
    print(mcu.baud_rate)
    print(mcu.is_connected)

    #验证通信
    print(mcu.ping())

    # 获取变量的值
    value = mcu.get("timerObj.timer_1sec_count")
    print(f"timerObj.timer_1sec_count = {value}")

    # 设置变量
    mcu.set("timerObj.timer_1sec_count", 0)


# 退出with语句,自动关闭串口
print(mcu.is_connected)


mcu = McuConnection()

#手动打开串口
mcu.open()

# 输出链接信息
print(mcu.port_name)
print(mcu.baud_rate)
print(mcu.is_connected)

#验证通信
print(mcu.ping())

# 获取变量的值
value = mcu.get("timerObj.timer_1sec_count")
print(f"timerObj.timer_1sec_count = {value}")

# 设置变量
mcu.set("timerObj.timer_1sec_count", 0)

#手动关闭串口
mcu.close()

