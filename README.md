This is a webservice for running an interface: and layer: index set 
for juju-compose. It is backed by mongo and can be quickstarted as follows

To test you can install docker and docker-compose

docker-compose up

make populate

browse to localhost:9999

to make juju-compose use this address you can pass --interface-service localhost:9999
on its cmd line
