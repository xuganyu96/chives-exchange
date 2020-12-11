# Order matching procedure 
The matching engine heartbeats for each time an incoming order message is received, and performs order matching for the incoming order within the heartbeat. There are several major steps in the order matching process:

## Finding matching candidates
This is implemented in `chives.matchingengine.MatchingEngine.get_candidates`

For a given incoming order, matching orders are defined by orders that satisfy the following conditions:
* it is active, as flagged by `active`
* it is on the opposite side as the incoming order
* it is not owned by the same user
* it has the same security symbol as the incoming order
* if the incoming order specifies a price, then candidate must offer an equal or better price: if the incoming order is a buy order, then the candidate must offer a cheaper price; if the incoming order is a sell order, then the candidate must offer a more expensive price

The sequence in which candidates are matched is first determined by their prices, then, in the case of a price tie, resolved by the order's `create_dttm`. This means that candidates that offer the best prices are matched first, and in case of a tied price, the older candidate is matched first.

## Proposing transaction
Given an incoming order and a matching candidate, a transaction is proposed with `chives.matchingengine.MatchingEngine.propose_trade`. 

If the candidate is all-or-none and the incoming order's remaining size cannot fulfill it completely, then this candidate is skipped (but remains active). Otherwise, the transaction size will be the minimum between the two order's remaining size, the price will be the candidate's price.

After a transaction is proposed, at least one between the incoming and the candidate is completely fulfilled. If the candidate is completely fulfilled then its order ID will be added to the list of IDs to be deactivated; if the candidate is partially fulfilled, then in addition to being added to the deactivation list, a sub-order will be created, flagged active, and added to the matching result as the `reactivated` candidate. It can be easily deduced that for each heartbeat, there can be at most 1 reactiavted candidate

On the other hand, if the incoming order has exhausted its remaining size, then we end the process of order matching; otherwise, the incoming order will be matched with the next candidate.

After all possible transactions are proposed, the remains of the incoming order is appropriately constructed: if no transaction is proposed, then the remain is the incoming itself; if the incoming is completely fulfilled, then the remain is `None`; if the incoming is partially fulfilled, then the remain is a sub-order of the incoming. In addition, the conditions for all-or-none and/or immediate-or-cancel policies are checked and appropriate changes made.

## The match result 
All database changes (excluding user logic) implied by a complete order matching cycle can be abstracted as four categories:
* changes to the incoming order, such as it becoming cancelled or active. For this the incoming order will be merged with the existing record in the database.
* the possibility of a distinct incoming order's remain. If there is indeed an incoming order's remain, then this remain will be added into the database as a new record
* all resting orders that were matched with the incoming order to produce transaction: they will be deactivated
* a possible suborder of a partially fulfilled candidate, which will be added into the database as a new record

In addition, there are a few user logics to be carried out:
* The seller will gain the cash (seller's stock reduction happens in webserver)
* The buyer will lose cash and gain stocks
* The company's market price will be updated with each transaction's price
* If the selling order has remaining portion that is cancelled, then the remaining portion is refunded back to the seller

## Database logging 
A number of logging messages that are added to the ORM session are sprinkled across the heartbeat. At the moment, the most important one is the one that says "heartbeat finished"

## Commit!
After all the changes are recorded in the session, the transaction will be flushed and committed (auto-flush is set to false so flush will only happen at the same time as commit). This means that with each heartbeat, the ORM session only commits once, which allows a simple rollback when SQL constraints that prevent double trading cause the commit to be rejected.