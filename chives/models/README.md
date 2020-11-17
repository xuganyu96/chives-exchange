# Chives exchange main database schema 
With each instance of the main database, we have the following tables:

## Users 
The `users` table contains user ID as a primary key, a unique username, 
a not-null password, and is primarily used for authentication. In future 
iterations, we should require that an email be used instead of a username.

## Asset 
The `assets` table abstracts the data of a user assets, which can be cash or 
stocks. Each user has exactly one portfolio with initial amount of cash, and 
each portfolio contains one of more entries, each signifying the holding of a 
kind of a security. For example:

|`owner_id`|`asset_symbol`|`asset_amount`|
|:---|:---|:---|
|`1`|`_CASH`|100000.00|
|`1`|`AAPL`|23000|
|`1`|`MSFT`|500000|

represents that user with id `1` has $100,000 in cash, 23,000 shares of apple
stocks, and 50,000 shares of microsoft stocks. Note that `_CASH` is has an 
underscore before it to prevent collision with an actual security with the 
symbol `CASH`. For cash, `asset_amount` is the immediate amount of cash; for 
securities, `asset_ammount` is the number of shares held. 

This table is updated each time a user submits an order (subtract cash if it is 
a buy order, or subtract shares if it is a sell order), and each time a 
transaction is committed into the database.

## Orders 
Each entry in the `orders` table represents a single stock order, or a suborder 
of a partially fulfilled order. In development environment, `owner_id` can be 
`NULL` for testing purposes, but with production, `owner_id` must not contain 
`NULL`'s.

## Transactions 
Each entry abstracts a committed trade that exchanges cash for securities.