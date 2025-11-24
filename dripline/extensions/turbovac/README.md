The files contained in telegram are a copy from the telegram folder of
https://github.com/fkivela/TurboCtl/tree/work
I modified the files to be compatible with python versions < 3.10, by changing some of the newer syntax features to clasical implementations.
We use the TurboCtl.telegram to generate the content of the telegram but use the dripline service to send it. Thus we can not make use of any of the other implementations.

The TurboVac Ethernet Service implements the USS protocol which consists of a STX-byte (\x02), LENGTH-byte, ADDRESS-byte, payload, XOR-checksum-byte.
The Payload is configured within the Endpoint class and makes use of the TurboCtl.telegram module. 
