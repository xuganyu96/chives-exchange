# Electronic Exchange
The chives exchange has the following components

## Order Queue
The order queue is a RabbitMQ server instance that contains as many queues as there are types of actively trading securities.

Order queue is aware of a table called `securities` in the SQL database that 
has two columns: `security_symbol` and `status`, where `security_symbol` is 
a string and a primary key, while `status` can be either `inactive` or `active`, 
as well. The securities table will have a record for each of security that can 
be traded on this platform.

When the webserver receives a POST request for submitting order, it needs to 
check if there is a corresponding matching engine already running. The 
webserver accomplishes this by checking the `securities` table, and the 
matching engine instance updates the `securities` table by having an 
asynchronous thread that for set interval of times, heartbeat the table with a
"now" timestamp.

## Matching Engine and Order Book
There is one matching engine instance for each type of security traded. Each matching engine runs a message callback method that heartbeats the engine instance each time an incoming order is captured. 

## Database
Since order books hold all orders in memory, the database serves as a permanent storage device for records that are more suitable for persistence, such as transaction histories.