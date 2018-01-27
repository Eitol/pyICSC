"""
ICSC protocol implementation


inspired on the python example of Majenko ICSC repo:
https://github.com/MajenkoLibraries/ICSC/tree/master/other/python
"""

import serial
import array
from curses.ascii import *

# IDX
SOH_IDX = 0
DEST_ID_IDX = 1
ORIG_ID_IDX = 2
CMD_IDX = 3
DAT_LEN_IDX = 4
STX_IDX = 5

ICSC_SYS_PING = ENQ  # 0x05
ICSC_SYS_PONG = ACK  # 0x06
ICSC_SYS_QSTAT = BEL  # 0x07
ICSC_SYS_RSTAT = BS  # 0x08
ICSC_BROADCAST = NUL  # 0x00
# Used when message is relayed to other station via a other station
ICSC_SYS_RELAY = HT  # 0x09

MIN_MSG_LEN = 9


class ICSC:
    class Config:
        ALLOW_DATA_WITH_BAD_CHECKSUM = False
        SEND_NUMBER_AS_STR = False

    def __init__(self, port, baud, station, config=Config):
        self.config = config
        self.commands_functions = {}
        # begin
        self.port = serial.Serial(port=port, baudrate=baud, timeout=1)
        self.station = ord(station) if isinstance(station, str) else station
        self.__init_port()
        self.commands_functions[ICSC_SYS_PING] = self.__respond_to_ping

    def __init_port(self):
        if self.port.is_open:
            self.port.close()
        self.port.open()

    def __standarize_params(self, destination, command, data):
        def str_to_bytes(data_):
            aux = data_
            data_ = array.array('B')
            data_.frombytes(aux.encode())
            return data_

        if isinstance(destination, str):
            destination = ord(destination)
        if isinstance(command, str):
            command = ord(command)
        if isinstance(data, str):
            data = str_to_bytes(data)
        elif isinstance(data, (int, float)):
            if self.config.SEND_NUMBER_AS_STR:
                data = str_to_bytes(str(data))
            else:
                data = array.array('B', [data])
        return destination, command, data

    @staticmethod
    def __calculate_checksum(header, data):
        return (sum(header) + sum(data)) % 256

    def __respond_to_ping(self, msg):
        self.send(msg['orig_id'], ICSC_SYS_PONG, [])

    def broadcast(self, command, data):
        self.send(ICSC_BROADCAST, command, data)

    def send(self, dest_id, cmd, data):
        dest_id, cmd, data = self.__standarize_params(dest_id, cmd, data)
        sendpacket = array.array('B',
                                 [
                                     SOH,
                                     dest_id,  # ID
                                     self.station,  # ORIG_ID
                                     cmd,  # CMD
                                     len(data),  # DATLEN
                                     STX]
                                 )
        sendpacket.extend(array.array('B', data))
        sendpacket.append(ETX)
        check_sum = self.__calculate_checksum([dest_id, self.station, cmd, len(data)], data)
        sendpacket.append(check_sum)
        sendpacket.append(EOT)
        self.port.write(sendpacket.tostring())

    def add_command(self, cmd: chr, f):
        if isinstance(cmd, str):
            cmd = ord(cmd)
        self.commands_functions[cmd] = f

    def extract_fields(self, data) -> dict:
        len_ = len(data)

        if len_ < MIN_MSG_LEN or len_ != MIN_MSG_LEN + data[DAT_LEN_IDX]:
            # BAD DATLEN
            return {}

        if data[DEST_ID_IDX] != self.station and data[DEST_ID_IDX] != ICSC_BROADCAST:
            return {}

        etx_idx = int(data[DAT_LEN_IDX]) + STX_IDX + 1
        eot_idx = int(data[DAT_LEN_IDX]) + STX_IDX + 3

        if data[SOH_IDX] != SOH or data[STX_IDX] != STX or data[etx_idx] != ETX or data[eot_idx] != EOT:
            return {}

        payload = data[STX_IDX:-4]  # STX -> ETX
        if not self.config.ALLOW_DATA_WITH_BAD_CHECKSUM:
            checksum_idx = len_ - 2
            header = [data[DEST_ID_IDX], data[ORIG_ID_IDX], data[CMD_IDX], data[DAT_LEN_IDX]]
            if not self.__calculate_checksum(header, payload) == data[checksum_idx]:
                return {}
        return {
            "dest_id": data[DEST_ID_IDX],
            "orig_id": data[ORIG_ID_IDX],
            "cmd": data[CMD_IDX],
            "dat_len": data[DAT_LEN_IDX],
            "data": payload
        }

    def process(self):
        in_data = self.port.read_until(bytearray([EOT]))
        msg = self.extract_fields(in_data)
        if 'cmd' in msg and msg['cmd'] in self.commands_functions:
            self.commands_functions[msg['cmd']](msg)
