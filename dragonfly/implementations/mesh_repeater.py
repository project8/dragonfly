'''
Implementing a provider which is a pure client in a second dripline mesh,
allowing a *one directional* link between otherwise independent meshes.
'''
from __future__ import absolute_import

import dripline
from dripline.core import Provider, Interface, Endpoint, fancy_doc

import logging
logger=logging.getLogger(__name__)

__all__ = ['MeshRepeater',
           'ProxyEndpoint',
          ]

@fancy_doc
class MeshRepeater(Provider):
    '''
    Provider which acts as a pure client on another dripline mesh.
    It provides a communication link, but does not do any communication itself.
    Instances of ProxyEndpoint can be added to bind targets on the local mesh to the remote mesh. (see ProxyEndpoint for more details)
    '''
    def __init__(self, target_broker, **kwargs):
        '''
        target_broker (str): network-resolvable path to the broker to which requests are relayed
        target_user (str): username used for connecting to the target mesh
        target_password (str): password used for connecting to the target mesh
        '''
        Provider.__init__(self, **kwargs)
        self._interface = Interface(amqp_url=target_broker, name=self.name+'_client')
        #self._interface.connect()

    def forward_request(self, target, request):
        '''send a request message to a target in the remote mesh

        target (str): full routing key to which request is sent
        request (RequestMessage): dripline.core.RequestMessage to send to target
        '''
        logger.warning('forwarding request')
        reply = self._interface.send_request(target, request)
        return reply

@fancy_doc
class ProxyEndpoint(Endpoint):
    '''
    Endpoint which responds to *all* RequestMessages received by passing them to the configured target via self.proivder (expected to be a MeshRepeater).
    '''

    def __init__(self, target, **kwargs):
        '''
        target: (str) name of the endpoint in the remote mesh, to which requests will be sent.
        '''
        Endpoint.__init__(self, **kwargs)
        self._target = target

    def handle_request(self, channel, method, properties, request):
        '''send reply message with to a target in the remote mesh

        channel (Channel): pika.Channel for interacting with RabbitMQ
        method: #TODO_DOC
        properties: #TODO_DOC
        request (RequestMessage): dripline.core.RequestMessage to send to target
        '''
        # This blindly sends *all* requests received to the target,
        # we could easily apply arbitrarly complex logic here if we wish to do so,
        # but it is not currently clear what that could/should be.
        # There is a certain cleanness to the current version.
        msg = dripline.core.Message.from_encoded(request, properties.content_encoding)
        logger.info("proxy forwarding request")
        reply = self.provider.forward_request(method.routing_key.replace(self.name, self._target, 1), msg)
        self.service.send_reply(properties, reply)
