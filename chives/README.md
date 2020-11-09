# Electronic Exchange
The chives exchange has the following components

## Order Queue
The order queue is a RabbitMQ server instance that contains as many queues as there are types of actively trading securities.

## Matching Engine and Order Book
There is one matching engine instance for each type of security traded. Each matching engine runs a message callback method that heartbeats the engine instance each time an incoming order is captured. 

## Database
Since order books hold all orders in memory, the database serves as a permanent storage device for records that are more suitable for persistence, such as transaction histories.