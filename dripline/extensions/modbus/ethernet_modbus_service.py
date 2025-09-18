try:
    import pymodbus
    from pymodbus.client import ModbusTcpClient
    from pymodbus.payload import BinaryPayloadDecoder
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
            if indexing.lower() == 'plc':
                self.offset = -1
            elif indexing.lower() == 'protocol':
                self.offset = 0
            else:
                raise ValueError('Invalid indexing string argument <{}>, expect <PLC> or protocol'.format(indexing))
        else:
            raise TypeError('Invalid indexing type <{}>, expect string or int'.format(type(indexing)))

        if wordorder.lower() == 'big':
            self.word = pymodbus.constants.Endian.BIG
        elif wordorder.lower() == 'little':
            self.word = pymodbus.constants.Endian.LITTLE
        else:
            raise ValueError('Invalid wordorder argument <{}>, expect big or little'.format(wordorder))

        if byteorder.lower() == 'big':
            self.byte = pymodbus.constants.Endian.BIG
        elif byteorder.lower() == 'little':
            self.byte = pymodbus.constants.Endian.LITTLE
        else:
            raise ValueError('Invalid byteorder argument <{}>, expect big or little'.format(byteorder))

        self.client = ModbusTcpClient(self.ip)
        self._reconnect()

    def _reconnect(self):
        '''
        Minimal connection method.
        TODO: Expand to call on failed read/write, and add sophistication.
        '''
        if self.client.connected:
            self.client.close()

        if self.client.connect():
            logger.debug('Connected to Alicat Device.')
        else:
            raise ThrowReply('resource_error_connection','Failed to Connect to Alicat Device')

    def read_register(self, register, n_reg, reg_type=0x04):
        '''
        n_reg determines the num of registers needed to express values. More n_reg are needed for higher accuracy values.
        reg_type: Lookup the endpoint code types that your device can access and specify in the code. 

        Expand as desired according to other calls in https://pymodbus.readthedocs.io/en/latest/source/client.html#modbus-calls
        '''
        logger.debug('Reading {} registers starting with {}'.format(n_reg, register))

        try:
            if reg_type == 0x03:
                result = self.client.read_holding_registers(register + self.offset, n_reg)
            elif reg_type == 0x04:
                result = self.client.read_input_registers(register + self.offset, n_reg)

            logger.info('Device returned {}'.format(result.registers))

        except Exception as e: 
            logger.debug(f'read registers failed: {e}. Attempting reconnect.')
            self._reconnect()

        if n_reg == 1:
            return result[0]
        else:
            return BinaryPayloadDecoder.fromRegisters(result.registers, wordorder=self.word, byteorder=self.byte)

    def write_register(self, register, value):
        '''
        This register only works with reg_type = 0x10
        '''
        logger.debug('writing {} to register {}'.format(value, register))   

        if not isinstance(value, list):
                raise ThrowReply('message_error_invalid_method', 'Unsupported write type')
        
        try:
            return self.client.write_registers(register + self.offset, value)
        
        except Exception as e:
            logger.debug(f'write_registers failed: {e}. Attempting reconnect.')
            self._reconnect()
            return self.client.write_registers(register + self.offset, value)


__all__.append('ModbusEntity')
class ModbusEntity(Entity):
    '''
    Generic entity for Modbus read and write.
    TODO: Add additional read-only or write-only versions
    '''
    def __init__(self,
                 register,
                 n_reg = 1,
                 data_type = None,
                 **kwargs):
        '''
        Args:
            register (int): address to read from
            n_reg (int): number of registers needed to read
            data_type (str): the data type being read from the registers
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
        logger.info('Decoded result for <{}> is {}'.format(self.name, result))
        return result

    def on_set(self, value):
        return self.service.write_register(self.register, value)
