# Main database and OrderBook database 
The main database is used for permanently recording the stock orders, 
transactions, as well as other tables for authentication/user management, etc.. 
The implementation of the main database is left to an existing major SQL 
database, such as MySQL, and is not meant to be interfaced frequently.

The OrderBook database (ob database for short) is used by a single instance of 
an order book within a matching engine to keep records of active orders. The ob 
database prioritizes low-latency operations but not otherwise high performance, 
so it should be implemented using a SQLite held in memory or in a local file.

The matching engine interfaces with both databases through SQLAlchemy's ORM 
module using two distinct engines wrapped in two distinct sessions. While the 
two databases are meant to be kept in sync (entries with the same ID across the 
two databases should be exactly identical), SQLAlchemy's ORM module does not 
allow a single ORM object to be committed into two distinct sessions. Most 
objects defined under `MatchingEngine` instance methods should be attached to 
the main database's session, while objects defined under `OrderBook` instance 
methods should be attached to the OB database. The sychronization is completed 
through Order objects' `.copy()` method.

# The matching engine heartbeat 
An instance of a matching engine heartbeats once for each time it receives an 
incoming order from the message queue. Within the heartbeat, the matching engine 
will compare the incoming order with existing active orders, and propose the 
set of changes to be committed into the main and ob database as the consequence 
of processing the incoming order.

The `match()` method of a matching engine instance returns the set of changes 
in an instance of the `MatchResult` class, which abstracts the fixed categories 
of database changes that can happen in a single round of order matching, which 
are as follows:

* The `incoming_order` may or may not have been cancalled due to it being both 
all-or-none and immediate-or-cancel, which means that it needs to be merged 
into the main database for reflecting the cancellation datetime
* There is a `incoming_remain` that falls into exactly one of the following 
three possibilities:
  * The `incoming_order` itself (which means `incoming_order is incoming_remain` 
  evaluates to True) for when the incoming order is all-or-none but not 
  completely fulfilled.  
  In this case, there is nothing to be done with this remains in the main 
  database since step 1 already committed all the changes into the main 
  database. On the other hand, if `incoming_remain` is active (or equivalently 
  not cancelled), then a copy of it should be added into the OB database
  * A suborder of the `incoming_order`, for when the incoming order is only 
  partially fulfilled and its remaining parts ready to be matched later.  
  In this case, the `incoming_remain` is distinct from the `incoming_order`, so 
  it needs to be first committed into the main database to get its `order_id`, 
  then, if this suborder is not yet cancelled, it should have a copy of itself 
  committed into the DB database
  * `None`, for when the incoming order is completely fulfilled.  
  In this case, do nothing with it
* `deactivated_candidates` are `order_id` of candidates from the order book that 
are non-trivially fulfilled. These orders should be change their `active` 
attribute to `False` in the main database, and their corresponding copies in 
the OB database will be removed based on their `order_id`.
* `reactivated_remain` is the sub-order of a partially fulfilled candidate. 
There should not be more than 1 of such sub-order. If `reactivated_remain` is 
`None`, do nothing; otherwise, this sub-order should first be committed into 
the main database, then a copy of it (which has an `order_id`) will be 
committed into the OB database.
* `transactions` are `Transaction` objects that record the trades that are 
proposed. They will be added into the main database in one swoop.

# Matching algorithm abstraction 
The implementation of the `match()` method roughly follows the logic below:
* Find all candidate orders from the order book, sorted from best to worst 
prices
* Iterate through this sorted list of candidate orders, at each candidate:  
  * Check if the `incoming_order` still has remaining shares to be traded; if 
  there is none left, `break`. Otherwise, propose a trade by creating a 
  `Transaction` object, which should deduct from each participating order's 
  remaining size, but also respect the candidate's policy (like AON).  
  If the `Transaction` object is non-trivial, then it should be appended to 
  `MatchResult.transactions`. In addition, the participating candidate should 
  be marked `inactive` and added to `deactivated_candidates`.  
  If the candidate is only partially fulfilled, then create a suborder and add 
  it to `MatchResult.reactivated_remain`. Again, there can be only up to one 
  reactivated remain
* After all matchings are complete, check incoming order's remaining size. If 
remaining size is exactly original size, then `MatchingResult.incoming_remain` 
is exactly `incoming_order`; if the remaining size is less then the original 
size, but greater than 0, then `MatchingResult.incoming_remain` is a sub-order 
of `incoming_order`; else, the remaining size is 0, so `incoming_remain` is 
`None`
* For each of the order policies of the incoming order that are checked "True",
apply the policy as function that mutates the `MatchResult`:
  * `all_or_none` checks for whether the sum of all transactions' size is less 
  than the incoming order's size. If True, then `transactions`, 
  `deactivated_candidates`, and `reactivated_remain` all revert to empty or 
  none, and `incoming_remain` points back to `incoming_order`
  * `immediate_or_cancel` checks for whether `incoming_remain` is `None`. If 
  not, then `incoming_remain` (which might be `incoming_order` due to having no 
  match, or due to `all_or_none`) will be cancelled.  
  Note that `IOC` must be respected after `AON` since `AON` affects which 
  order is cancelled by `IOC`.
