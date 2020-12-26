# Matching engine 
A matching engine is the software that accepts submitted stock orders from a message queue and process them by matching them against resting orders in the order book, and committing trades and other changes to the database.

## data structure & matching algorithm overview 
The core data structure that a matching engine interacts with includes `orders` and `transactions`; if `ignore_user_logic` is set to `False`, then a matching engine also interacts with `users`, `assets`, and `companies`. Finally, it logs itself using the `me_logs`.

### the match result 
There are 5 categories of ORM transactions that each match cycle produces, all of which are captured as instance attributes of a `MatchResult` object:

1. **The `incoming_order` might be mutated**  
Such as in the case that the `incoming_order` is AON and IOC and not fully fulfilled, which will result in its `cancelled_dttm` being filled with a time stamp (the `active` flag is False by default), or in the case when `incoming_order` is not fulfilled at all but not IOC, which will result in its `active` flag being marked `True`, signifying that the incoming order becomes a resting order.  
In all cases, the `incoming_order` object, mutated or not, will be merged into the session
2. **The `incoming_order` might produce a non-trivial sub-order**  
If the `incoming_order` is completely fulfilled or not fulfilled at all, then no sub-order will be created. Otherwise, what remains of the `incoming_order` will become a suborder that, depending on whether `incoming_order`is IOC, will either become an active resting order or be cancelled. If the `incoming_remain` is not `None` nor `incoming_order` itself, then it will be added into the session as a new entry. Note that because it is a new order, it will not have a `order_id` upon creation, but obtain it once it is written into the database.
3. **A number of candidates will be mutated**  
All candidate resting orders with which the `incoming_order` traded will see their `active_flag` set to `False`.
4. **A sub-order of a partially fulfilled candidate might be added**  
In the case where a candidate order is only partially fulfilled, its remaining part will be made into a suborder that will be added into the database. Note that logically speaking, there cannot be two or more candidate orders that are only partially fulfilled, so this `sub-order` is either `None` or unique.
5. **New transactions**  
All the new `transaction` objects will be added to the database

### User logic (if not `ignore_user_logic`)
1. **exchange of assets to respective users**  
For each transaction, the owner of the bid is the buyer (of stocks) and the owner of the ask is the seller. The buyer gains stocks and loses cash, while the seller gains cash and loses stock. This is reflected in their corresponding entries in the `assets` table. Note that "seller loses stocks" is not explicitly implemented in the `exchange_user_asset` because in the webserver, upon submitting a selling order, the input number of stocks to sell (the order size) is already subtracted from the seller's asset
2. **update company market price**  
For each transaction, the transaction price will be the most updated `company.market_price` to the company that this transaction is acting on
3. **refund cancelled remains**  
For a selling order, if what remains of it (possibly the entire order or a suborder) is cancelled, as indicated by a non-trivial `cancelled_dttm`, then the size of the remaining order will be added back to the seller's asset.

### Logging 
For now the engine will write a `process complete` message to the database at the end of each match cycle. This will be used by the `benchmark` module to determine if all dummy orders have been processed.

## heartbeat 
For a given matching engine instance `me: chives.MatchingEngine` with a SQLAlchemy ORM session `me.session`, the `me.heartbeat()` method is called each time the `pika` client receives a message from the message queue.

The message queue will give at most one message to each matching engine and will not receive acknowledgement for the dispatched message until the matching engine successfully processes the order in the dispatched message. This is implemented on the assumption that the matching engine will process an order faster than a message is timed-out, which should be truly all the time.

The `me.heartbeat()` method takes an `chives.models.Order` object as the only argument. Note that because the entire heartbeat method is designed to do exactly one commit (a design choice that will be discussed later), it will require that the input `Order` object has a valid `order_id` that maps it to an order entry in the SQL database's `orders` table.

In a single heartbeat, there are two major steps: `me.match` and `me.process_match_result`. The former reads candidate resting orders from the SQL database, proposes trades, and produces a `match_result: MatchResult` object that abstracts the various kinds of changes (to the database) each matching cycle brings. The `match_result` object is then passed into the `me.process_match_result` method, which will create the appropriate ORM transaction(s) into the session and try to commit them.

## Single-commit cycle and race condition 
When there are more than one matching engine(s) running, there is the possibility of the following race condition that results in an inconsistent state for the database:

Suppose there are two matching engines `me_1` and `me_2` running at the same time, and they received `order_1` and `order_2` respectively at roughly the same moment. In addition, `order_0` is an entry in the database that both `order_1` and `order_2` can be matched with, so it will be picked up by both `me_1` and `me_2`, which results in `order_0` being traded twice.

To counter this race condition, a SQL database constraint is placed in the `transaction` table such that each transaction's `resting_order_id` must be unique; a similar constraint is forced on `orders.parent_order_id` to ensure that the same resting order is not picked up twice by two distinct matching engines. Note that only `resting_order_id` needs to be unique; `aggressor_order_id` does not need to be unique because a big aggressor order can be matched with multiple resting orders, thus producing multiple transactions on the same aggressor order. On the other hand, if a resting order is partially fulfilled, then a sub-order will be created with a different `order_id`. With this database constraint in place, when the scenario above plays out, whichever matching engine commits later will see its commit rejected, at which point it will rollback all of its transactions in its session and repeat its heartbeat in a recursive fashion:

```python
def heartbeat(self, order):
    try:
        self._heartbeat(order)
    except:
        self.session.rollback()
        self.heartbeat(order)
```

To keep this `try-commit-except-rollback` cycle clean, a few design decisions were made to make sure that the matching engine does not "commit partial changes," and one of them was that each cycle would see exactly one commit at the end of everything.