# Order matching procedure 
The matching engine heartbeats for each time an incoming order message is received, and performs order matching for the incoming order within the heartbeat. There are several major steps in the order matching process:

1. [(Optional) Add incoming order into the database](#add-incoming-order-into-database)
2. Find matching candidates from resting orders
3. Commit matching results
4. (Optional) Perform user logic

## Add incoming order into database
This step is optional and canonically skipped.

The canonical method through which a stock order is submitted is through the webserver, and the `/exchange/submit_order` route implementation will add the newly created `Order` object into the ORM session and commit it into the database before submitting it into the message queue to be processed by the matching engine. As a result, it should be expected that the order object reconstructed from the messsage contains an `order_id` that correctly corresponds to the entry in the database.

However, for increased flexibility, especially with benchmarking and testing, orders without `order_id` are allowed to be received by the matching engine