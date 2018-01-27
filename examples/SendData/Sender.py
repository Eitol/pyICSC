from pyICSC import ICSC

if __name__ == '__main__':
    config = ICSC.Config()
    config.SEND_NUMBER_AS_STR = True
    icsc = ICSC("/dev/ttyACM0", 115200, 'B', config)
    # Send: 01 41 42 58 04 02 35 33 32 33 03 ac 04
    icsc.send('A', 'X', 5323)
    # Send: 01 41 42 58 08 02 48 4f 4c 41 41 41 41 41 03 0b 04
    icsc.send('A', 'X', "HOLAAAAA")
    # Send: 01 41 42 58 04 02 01 52 63 85 03 1a 04
    icsc.send('A', 'X', [0x01, 0x52, 0x63, 0x85])
