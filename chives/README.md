# Electronic Exchange
The chives exchange has the following components

## Web Client 
* Submit order to inbound order queues
* Read information from the web server

## Client Queue
* Accepts order submission from web clients

## Trading Floor 
* A trading floor is a collection of trading floor workers
* Each worker has access to the list of actively trading securities
* Each worker periodically scans every single inbound client queue and pulls in one order at the time
    * If the order is trading on an actively trading security, then send the order to the appropriate order queue
    * If the order is trading on a new security, then spin up a new pair of order queue and order book for the new security

## Order queue and order book
An order queue of a specific security accepts orders that trade on that specific security. 

An order book of a specific security periodically polls the order queue for arriving order, tries to match the arriving order with existing active orders, and executes trades based on the order's attributes such as target price and order type. 

## Database
Since order books hold all orders in memory, the database serves as a permanent storage device for records that are more suitable for persistence, such as transaction histories.

## Web server 
A backend server for serving data from the database to the web client. It is also responsible for handling user authentication.