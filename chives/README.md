# Electronic Exchange
The chives exchange has the following components

## Web Client 
* Submit order to inbound order queues
* Read information from the web server

## Trading Floor
The trading floor is the HTTP server that accepts order submissions and cancellation requests from the web client (and exactly those two things; the rest is handled by another dedicated webserver that will be explained below).

When the HTTP server accepts an order submission, it checks whether it is a valid security, then checks if there is a corresponding matching engine that is running. If no corresponding matching engine instance is running, it will spawn one, then forwards the order submission to an appropriately named queue in the order queue instance.

 It will also serve information to the user, but the user interface part will be implemented later.

## Order Queue
The order queue is a RabbitMQ server instance that contains as many queues as there are types of actively trading securities.

## Matching Engine and Order Book
There is one matching engine instance for each type of security traded. Each matching engine runs a message callback method that heartbeats the engine instance each time an incoming order is captured. 

## Database
Since order books hold all orders in memory, the database serves as a permanent storage device for records that are more suitable for persistence, such as transaction histories.