try:
    import pymodbus
    from pymodbus.client import ModbusTcpClient
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
                 **kwargs
                 ):
        '''
        Args:
            ip_address (str): properly formatted ip address of Modbus device
            indexing (int, str): address indexing used by device
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

        self.client = ModbusTcpClient(self.ip)
        self._reconnect()

    def _reconnect(self):
        '''
        Minimal connection method.
        '''
        if self.client.connected:
            self.client.close()

        if self.client.connect():
            logger.debug('Connected to Device.')
        else:
            raise ThrowReply('resource_error_connection','Failed to Connect to Device')

    def read_register(self, register, n_reg, reg_type=0x04):
        '''
        n_reg determines the num of registers needed to express values. More n_reg are needed for higher accuracy values.
        reg_type: Lookup the endpoint code types that your device can access and specify in the code. 

        Expand as desired according to other calls in https://pymodbus.readthedocs.io/en/latest/source/client.html#modbus-calls
        '''
        logger.debug('Reading {} registers starting with {}'.format(n_reg, register))

        try:
            if reg_type == 0x03:
                result = self.client.read_holding_registers(register + self.offset, count=n_reg)
            elif reg_type == 0x04:
                result = self.client.read_input_registers(register + self.offset, count=n_reg)

            logger.info('Device returned {}'.format(result.registers))

        except Exception as e: 
            logger.debug(f'read registers failed: {e}. Attempting reconnect.')
            self._reconnect()
            try:
                if reg_type == 0x03:
                    result = self.client.read_holding_registers(register + self.offset, count=n_reg)
                elif reg_type == 0x04:
                    result = self.client.read_input_registers(register + self.offset, count=n_reg)
    
                logger.info('Device returned {}'.format(result.registers))
    
            except Exception as e: 
                raise ThrowReply('resource_error_query', 'Query data failed')


        if n_reg == 1:
            return result.registers[0]
        else:
            return result.registers

    def write_register(self, register, value):
        '''
        This register uses reg_type = 0x10 if value is a list and reg_type = 0x06 otherwise.
        '''
        logger.debug('writing {} to register {}'.format(value, register))   

        try:
            if isinstance(value, list):
                return self.client.write_registers(register + self.offset, value).registers
            else:
                return self.client.write_register(register + self.offset, value).registers[0]
        except Exception as e:
            logger.debug(f'write_registers failed: {e}. Attempting reconnect.')
            self._reconnect()
            try:
                if isinstance(value, list):
                    return self.client.write_registers(register + self.offset, value).registers
                else:
                    return self.client.write_register(register + self.offset, value).registers[0]
            except:
                raise ThrowReply('resource_error_write','Failed to write register')

__all__.append('ModbusEntity')
class ModbusEntity(Entity):
    '''
    Generic entity for Modbus read and write.
    TODO: Add additional read-only or write-only versions
    '''
    def __init__(self,
                 register,
                 n_reg = 1,
                 wordorder = "big",
                 data_type = None,
                 reg_type = 0x04,
                 **kwargs):
        '''
        Args:
            register (int): address to read from
            n_reg (int): number of registers needed to read
            data_type (str): the data type being read from the registers
        '''
        self.register = register
        self.n_reg = n_reg
        self.reg_type = reg_type
        self.wordorder = wordorder
        self.data_type = data_type
        Entity.__init__(self, **kwargs)

    @calibrate()
    def on_get(self):
        result = self.service.read_register(self.register, self.n_reg, self.reg_type)
        if self.data_type == 'float32':
            result = ModbusTcpClient.convert_from_registers(result, ModbusTcpClient.DATATYPE.FLOAT32, word_order=self.wordorder)
        logger.info('Decoded result for <{}> is {}'.format(self.name, result))
        return result

    def on_set(self, value):
        return self.service.write_register(self.register, value)
