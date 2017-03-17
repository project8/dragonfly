'''
Implementing a provider which is a pure client in a second dripline mesh,
allowing a *one directional* link between otherwise independent meshes.
'''
from __future__ import absolute import

from dripline.core import Provider

import logging
logger=logging.getLogger(__name__)

__all__ = ['MeshRepeater',
          ]

class MeshRepeater(Provider):
    '''
    Provider which acts as a pure client on another dripline mesh.
    It provides a communication link, but does not do any communication itself.
    Instances of ProxyEndpoint can be added to bind targets on the local mesh to the remote mesh. (see ProxyEndpoint for more details)
    '''
    def __init__(self, target_broker, target_user, target_password, **kwargs):
        '''
        target_broker: (str) network-resolvable path to the broker to which requests are relayed
        target_user: (str) username used for connecting to the target mesh
        target_password: (str) password used for connecting to the target mesh
        '''
        Provider.__init(**kwargs):
        self._mesh_credentials = {'host': target_broker,
                                  'username': target_user,
                                  'password': target_password,
                                 }
        # create a(n Interface?) instance (service? what exists now...) for use
        #self._interface = <something here>

    def send_request(self, target, request):
        '''send a request message to a target in the remote mesh

        target: (str) full routing key to which request is sent
        request: (RequestMessage) dripline.core.RequestMessage to send to target
        '''
        # use self._interface to send <request> to <target>, return the result
        pass



class ProxyEndpoint(Endpoint):
    '''
    Endpoint which responds to *all* RequestMessages received by passing them to the configured target via self.proivder (expected to be a MeshRepeater).
    '''
    # design question: should this class blindly send literally *all* requests to its target?
    # if so that's easy, just override handle_request to send the message
    # alternately, the core methods (such as lock and ping) could apply to the proxy itself, not the target.
    #... I have no idea which behavior represents "least surprise" for a reasonable user
    #(the service itself will still support locking and such... perhaps I start with the first option)

    def __init__(self, target, **kwargs):
        Endpoint.__init__(self, **kwargs)
        self._target = target

    def handle_requests(self, channel, method, properties, request):
        # This blindly sends *all* requests received to the target,
        # we could easily apply arbitrarly complex logic here if we wish to do so,
        # but it is not currently clear what that could/should be.
        # There is a certain cleanness to the current version.
        self.provider.send_request(method.routing_key.(self.name, self._target, 1)
