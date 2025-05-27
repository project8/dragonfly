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
                 **kwargs
                 ):
        '''
        Args:
            ip_address (str): properly formatted ip address of Modbus device

        '''
        if not 'pymodbus' in globals():
            raise ImportError('pymodbus not found, required for EthernetModbusService class')

        Service.__init__(self, **kwargs)

        self.ip = ip_address
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

    def read_register(self, register):
        '''
        Currently only register read type #4, read_input_registers, is implemented.
        Expand as desired according to other calls in https://pymodbus.readthedocs.io/en/latest/source/client.html#modbus-calls
        '''
        logger.debug('Reading register {}'.format(register))
        try:
            result = self.client.read_holding_registers(register, count=1)
        except Exception as e:
            logger.debug(f'read_holding_registers failed: {e}. Attempting reconnect.')
            self._reconnect()
            result = self.client.read_holding_registers(register, count=1)

        logger.debug('Device returned {}'.format(result.registers))
        return result.registers

    def write_register(self, register, value):
        logger.debug('writing {} to register {}'.format(value, register))
        try:
            response = self.client.write_register(register, value)
        except Exception as e:
            logger.debug(f'write_registers failed: {e}. Attempting reconnect.')
            self._reconnect()
            response = self.client.write_register(register, value)

        logger.debug('device respond with {} '.format(response))
        return value


__all__.append('ModbusEntity')
class ModbusEntity(Entity):
    '''
    Generic entity for Modbus read and write.
    TODO: Add additional read-only or write-only versions
    '''
    def __init__(self,
                 register,
                 **kwargs):
        self.register = register
        Entity.__init__(self, **kwargs)

    @calibrate()
    def on_get(self):
        result = self.service.read_register(self.register)
        return result[0] 

    def on_set(self, value):
        return self.service.write_register(self.register, value)
