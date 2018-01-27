import time

from pyICSC import ICSC

if __name__ == '__main__':
    foo = ICSC("/dev/ttyACM0", 115200, 'A')
    foo.send('B', 'P', [])  # list(map(int, "PRESS")))
    time.sleep(2)
    foo.send('B', 'R', [])  # list(map(int, "PRESS")))
