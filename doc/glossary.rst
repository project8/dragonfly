.. _parlance:

########
Glossary
########

.. glossary:: :sorted:

    endpoint
        A logical destination in the slow control sysem to which requests may be sent. An endpoint may represent something physical, or something abstract. The pressure or temperature reading for a particular instrument, or the instrument itself would be an example. More precisely, it is an component of code which is able to acton in accordance to the msgop received in a request message and produces the result(s) for a reply message.

    gogol
        A special case of :term:`provider` which is intended to be a top level object in a service configuration and binds to the "alerts" queue. This is the generic class which is used by services which generally provide some level of logic based on the broadcasts being made by other services (usually a :term:`spimescape`\s).

    provider
        A subset of :term:`endpoint`\ s which can "provide" access to or interpretation for a set of endpoints. Providers, for example, are responsible for taking the raw SCPI command for reading a particular quantity (which and endpoint knows it wants to issue) and actually sending it over a network socket to a physical device and getting a response.

    message
        An object delivered by AMQP and conformant to the :ref:`wire-protocol` .

    mesh
        The complete set of components in a slow control system. It is centered around an AMQP server (such as rabbitmq) and referrs to everything connected to it.

    service
        A long running process which is part of the :term:`mesh`. This is similar to a daemon process on linux systems except that a daemon process is one which explicitly is run in the background, whereas a dripline service is commonly run in forground but detached (we use tmux, but screen would also serve).

    spime
        A subset of :term:`endpoint`\s which also inherit from the "Scheduler" class. A scheduler is able to perform an action repeatedly at regular intervals, usually logging the result of self.on_get, but possibly other action.

    spimescape
        A special case of :term:`provider` which is intended to be a top level object in a service configuration and binds to the "requests" queue. This is the generic class which is used by services which generally provide access to instruments and other endpoints.
