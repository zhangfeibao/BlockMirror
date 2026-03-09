from ramgs.testkit import McuConnection

with McuConnection() as mcu:
    print(mcu.port_name)
    print(mcu.baud_rate)
    print(mcu.ping())
    


