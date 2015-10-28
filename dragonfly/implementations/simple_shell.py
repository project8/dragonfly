from __future__ import absolute_import

from subprocess import check_output
import logging

from dripline.core import Provider, Endpoint, Spime, calibrate

__all__ = ['simple_shell_instrument', 'simple_shell_command',
           'sensors_command_temp']
logger = logging.getLogger(__name__)

class simple_shell_instrument(Provider):
    def __init__(self, name, **kwargs):
        Provider.__init__(self, name=name, **kwargs)

    def list_endpoints(self):
        return self.endpoints.keys()

    def endpoint(self, endpoint):
        if endpoint in self.list_endpoints():
            return self.endpoints[endpoint]

    def send(self, to_send):
        raw_result = None
        if to_send:
            logger.debug('going to execute:\n{}'.format(to_send))
            try:
                raw_result = check_output(to_send)
            except OSError:
                raise exceptions.DriplineHardwareError('this server does not support <{}>\nconsider installing it'.format(to_send))
            logger.debug('raw is: {}'.format(raw_result))
        return raw_result


class simple_shell_command(Spime):
    def __init__(self, get_cmd_str=None, set_cmd_str=None, **kwargs):
        logger.info('kwargs are:\n{}'.format(kwargs))
        Spime.__init__(self, **kwargs)
        self._get_str = get_cmd_str
        self._set_str = set_cmd_str

    def on_get(self):
        result = self.provider.send(self._get_str)
        return result

    def on_set(self, value):
        result = self.provider.send(self._get_str.format(value))
        return result


# WARNING, this is not even close to portable
class sensors_command_temp(simple_shell_command):
    '''
    Temperature sensors on higgsino
    
    This assumes that the "sensors" command is installed, which it probably isn't.
    '''
    def __init__(self, core=0, **kwargs):
        super(sensors_command_temp, self).__init__(get_cmd_str='sensors', **kwargs)
        self._core = core

    @calibrate()
    def on_get(self):
        result = None
        res_lines = super(sensors_command_temp, self).on_get()
        for line in res_lines.split('\n'):
            logger.info('looking at line:\n{}'.format(line))
            if line.startswith('Core {}:'.format(self._core)):
                result = line.split()[2].replace('\xc2\xb0', ' ')
        return result
