"""
ICSC protocol implementation


inspired on the python example of Majenko ICSC repo:
https://github.com/MajenkoLibraries/ICSC/tree/master/other/python
"""
from enum import IntEnum
import timeout_decorator

import serial
import array
from curses.ascii import *

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


class FlowError(IntEnum):
    NO_ERROR = 0
    BAD_FORMAT = 1
    VOID_MSG = 2
    TO_SHORT_MSG = 3

    # Logical errors
    UNEXPECTED_ORIGIN = 3
    UNEXPECTED_CMD = 4
    WRONG_DEST_STATION = 5

    # Meta data fields errors
    BAD_LEN_FIELD = 6
    BAD_CHECKSUM = 7

    # Control fields errors
    MISSING_SOH = 8
    MISSING_STX = 9
    MISSING_ETX = 10
    MISSING_EOT = 11


class ICSC:
    class Config:
        # Indicates that you want to accept messages with wrong checksum
        ALLOW_DATA_WITH_BAD_CHECKSUM = False

        # If true, then the numbers will be sent as string
        SEND_NUMBER_AS_STR = False

        # maximum time between messages
        PROCESS_TIMEOUT = 1

        # If is true then print some debug text
        DEBUG = True

        # function that is executed when a timeout occurs.
        # You can use to detect anomalies in communication
        ON_TIMEOUT_CALLBACK = None

    def __init__(self, port, baud, station, config=Config):
        self.config = config
        self.commands_functions = {}
        self.port = serial.Serial(port=port, baudrate=baud,
                                  timeout=config.PROCESS_TIMEOUT,
                                  parity='N', stopbits=1, bytesize=8)
        self.station = ord(station) if isinstance(station, str) else station
        self.__init_port()
        self.commands_functions[ICSC_SYS_PING] = self.__respond_to_ping

    def __init_port(self):
        if self.port.is_open:
            self.port.close()
        self.port.open()

    def __standardize_params(self, destination, command, data):
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
    def calculate_checksum(header, data):
        return (sum(header) + sum(data)) % 256

    def __respond_to_ping(self, msg):
        self.send(msg['orig_id'], ICSC_SYS_PONG, [])

    def broadcast(self, command, data):
        self.send(ICSC_BROADCAST, command, data)

    def send(self, dest_id: object, cmd: object, data: object) -> None:
        dest_id, cmd, data = self.__standardize_params(dest_id, cmd, data)
        sendpacket = array.array('B',
                                 [
                                     SOH,
                                     dest_id,  # ID
                                     self.station,  # ORIG_ID
                                     cmd,  # CMD
                                     len(data),  # DATLEN
                                     STX
                                 ])
        sendpacket.extend(array.array('B', data))
        sendpacket.append(ETX)
        check_sum = self.calculate_checksum([dest_id, self.station, cmd, len(data)], data)
        sendpacket.append(check_sum)
        sendpacket.append(EOT)
        if self.config.DEBUG:
            print("SEND: {}".format(sendpacket.tobytes()))
        self.port.write(sendpacket.tobytes())

    def add_command(self, cmd: chr, f):
        if isinstance(cmd, int):
            cmd = chr(cmd)
        self.commands_functions[cmd] = f

    @staticmethod
    def validate_fields(data, etx_idx: int, eot_idx: int) -> FlowError:
        if data[SOH_IDX] != SOH:
            return FlowError.MISSING_SOH
        if data[STX_IDX] != STX:
            return FlowError.MISSING_STX
        if data[etx_idx] != ETX:
            return FlowError.MISSING_ETX
        if data[eot_idx] != EOT:
            return FlowError.MISSING_EOT
        return FlowError.NO_ERROR

    def extract_fields(self, data) -> (FlowError, dict):
        len_ = len(data)

        if len_ < MIN_MSG_LEN:
            return FlowError.TO_SHORT_MSG, {}

        if len_ != MIN_MSG_LEN + data[DAT_LEN_IDX]:
            return FlowError.BAD_LEN_FIELD, {}

        if data[DEST_ID_IDX] != self.station and data[DEST_ID_IDX] != ICSC_BROADCAST:
            return FlowError.WRONG_DEST_STATION, {}

        etx_idx = int(data[DAT_LEN_IDX]) + STX_IDX + 1
        eot_idx = etx_idx + 2

        field_error = self.validate_fields(data, etx_idx, eot_idx)
        if field_error != FlowError.NO_ERROR:
            return field_error, {}

        payload = data[STX_IDX + 1:-3]  # STX -> ETX
        if not self.config.ALLOW_DATA_WITH_BAD_CHECKSUM:
            checksum_idx = len_ - 2
            header = [data[DEST_ID_IDX], data[ORIG_ID_IDX], data[CMD_IDX], data[DAT_LEN_IDX]]
            if not self.calculate_checksum(header, payload) == data[checksum_idx]:
                return FlowError.BAD_CHECKSUM, {}

        return (FlowError.NO_ERROR, {
            "dest_id": chr(data[DEST_ID_IDX]),
            "orig_id": chr(data[ORIG_ID_IDX]),
            "cmd": chr(data[CMD_IDX]),
            "dat_len": data[DAT_LEN_IDX],
            "data": payload
        })

    def read_from_serial(self) -> bytearray:
        in_data = b''
        try:
            in_data = self.port.read_until(bytearray([EOT]))
        except TimeoutError:
            if self.config.ON_TIMEOUT_CALLBACK is not None:
                self.config.ON_TIMEOUT_CALLBACK()
        return in_data

    @staticmethod
    def is_truncated_msg(in_data: bytearray, error: FlowError) -> bool:
        return in_data.endswith(bytearray([EOT])) and error == FlowError.BAD_LEN_FIELD

    def get_msg(self, in_data: bytearray) -> (FlowError, dict):
        error, msg = self.extract_fields(in_data)
        if self.is_truncated_msg(in_data, error):
            remaining_eot = self.read_from_serial()
            if remaining_eot != EOT:
                return FlowError.BAD_FORMAT, {}
            in_data.append(EOT)  # == in_data + remaining_eot
            return self.extract_fields(in_data)
        return error, msg

    @timeout_decorator.timeout(5)
    def process(self) -> (FlowError, dict):
        while True:
            in_data = self.read_from_serial()
            if len(in_data) == 0:
                continue
            error, msg = self.get_msg(in_data)
            if error != FlowError.NO_ERROR:
                return error, {}
            if self.config.DEBUG:
                print("IN DATA: {}".format(in_data))
                print("IN MSG: {}".format(in_data))
            if 'cmd' in msg and msg['cmd'] in self.commands_functions:
                self.commands_functions[msg['cmd']](msg)
            return FlowError.NO_ERROR, msg
