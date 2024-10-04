try:
    import pymodbus
except ImportError:
    pass

import scarab

from dripline.core import calibrate, Entity, Service, ThrowReply

import logging
logger = logging.getLogger(__name__)

__all__ = []


__all__.append('EthernetModbusService')
class EthernetModbusService(Service):
    '''
    Service for connectivity to ModbusTCP instruments built on pymodbus library.
    '''
    def __init__(self,
                 ip_address,
                 indexing='protocol',
                 wordorder='big',
                 byteorder='big',
                 **kwargs
                 ):
        '''
        Args:
            ip_address (str): properly formatted ip address of Modbus device
            indexing (int, str): address indexing used by device
            wordorder (str): endianness of reply words
            byteorder (str): endianness of reply bytes
        '''
        if not 'pymodbus' in globals():
            raise ImportError('pymodbus not found, required for EthernetModbusService class')

        Service.__init__(self, **kwargs)

        self.ip = ip_address
        if isinstance(indexing, int):
            self.offset = indexing
        elif isinstance(indexing, str):
            if lower(indexing) == 'plc':
                self.offset = -1
            elif lower(indexing) == 'protocol':
                self.offset = 0
            else:
                raise ValueError('Invalid indexing string argument <{}>, expect <PLC> or protocol'.format(indexing))
        else:
            raise TypeError('Invalid indexing type <{}>, expect string or int'.format(type(indexing)))

        if lower(wordorder) == 'big':
            self.word = pymodbus.constants.Endian.BIG
        elif lower(wordorder) == 'little':
            self.word = pymodbus.constants.Endian.LITTLE
        else:
            raise ValueError('Invalid wordorder argument <{}>, expect big or little'.format(wordorder))

        if lower(byteorder) == 'big':
            self.byte = pymodbus.constants.Endian.BIG
        elif lower(byteorder) == 'little':
            self.byte = pymodbus.constants.Endian.LITTLE
        else:
            raise ValueError('Invalid byteorder argument <{}>, expect big or little'.format(byteorder))

        self._reconnect()

    def _reconnect(self):
        '''
        Minimal connection method.
        TODO: Expand to call on failed read/write, and add sophistication.
        '''
        self.client = pymodbus.client.ModbusTcpClient(self.ip)

        if client.connect():
            logger.debug('Connected to Alicat Device.')
        else:
            raise ThrowReply('resource_error_connection','Failed to Connect to Alicat Device')

    def read_register(self, register, n_reg, reg_type=0x04):
        '''
        Currently only register read type #4, read_input_registers, is implemented.
        Expand as desired according to other calls in https://pymodbus.readthedocs.io/en/latest/source/client.html#modbus-calls
        '''
        logger.debug('Reading {} registers starting with {}'.format(n_reg, register))
        if reg_type == 0x04:
            result = self.client.read_input_registers(register+offset, n_reg)
        else:
            raise ThrowReply('message_error_invalid_method', 'Register type {} not supported'.format(reg_type))
        logger.info('Device returned {}'.format(result))
        return pymodbus.payload.BinaryPayloadDecoder.fromRegisters(result.registers, wordorder=self.word, byteorder=self.byte)

    def write_register(self, register, value):
        if not isinstance(value, list):
            raise ThrowReply('message_error_invalid_method', 'Unsupported write type')
        return self.client.write_register(register+offset, value)


__all__.append('ModbusEntity')
class ModbusEntity(Entity):
    '''
    Generic entity for Modbus read and write.
    TODO: Add additional read-only or write-only versions
    '''
    def __init__(self,
                 register,
                 n_reg,
                 data_type,
                 **kwargs):
        '''
        '''
        self.register = register
        self.n_reg = n_reg
        self.data_type = data_type
        Entity.__init__(self, **kwargs)

    @calibrate()
    def on_get(self):
        result = self.service.read_register(self.register, self.n_reg)
        if self.data_type == 'float32':
            result = result.decode_32bit_float()
        logger.info('Decoded result is {}'.format(result))
        return result

    def on_set(self, value):
        return self.service.write_register(self.register, value)
