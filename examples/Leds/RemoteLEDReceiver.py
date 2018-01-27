from pyICSC import ICSC

"""
Python version for RemoteLEDReceiver.ino
Link: 
https://github.com/MajenkoLibraries/ICSC/blob/master/examples/RemoteLEDReceiver/RemoteLEDReceiver.ino
"""

if __name__ == '__main__':
    icsc = ICSC("/dev/ttyACM0", 115200, 'B')
    icsc.add_command('P', lambda x: print("PRESS"))
    icsc.add_command('R', lambda x: print("RELEASE"))
    while True:
        icsc.process()
