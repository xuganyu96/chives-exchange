# Matching algorithm
Some pseudo-code:
```python
transactions = []
# Store a copy of the incoming order in the database. In subsequent code, various attributes of 
# incoming may be changed, but can be restored by incoming.revert(), or committed by 
# incoming.commit()
incoming.commit()

if incoming.side == "buy":
    incoming_bid = incoming
    is_opposite_side = (active_orders.side == "sell")
    candidate_asks = active_orders.query.filter(is_opposite_side)

    # If the incoming bid has a target price, then it is a limit order, so it will only be 
    # matched with active selling orders at equal or lower selling prices;
    # Otherwise, the incoming bid buys at market price, so it will be matched with all active
    # selling orders
    if incoming_bid.target_price:
        is_valid_price = (active_orders.target_price <= incoming_bid.target_price)
        candidate_asks = active_orders.query.filter(is_opposite_side).filter(is_valid_price)
    candidate_asks = candidate_asks.orderby('target_price', ascending=True)

    # If the cheapest of all selling prices is higher then the incoming bid's price, 
    # then the for loop below will simpll be skipped;
    # in addition, because of the "orderby" above, this for-loop will begin with the lowest 
    # selling ask and iterates with increasing selling price
    matched_asks = []
    for candidate_ask in candidate_asks:
        if not incoming_bid.size <= 0:
            # if the incoming_bid is already entirely fulfilled, then there is no need for 
            # additional transactions.
            if (incoming_bid.size >= candidate_ask.size) or (not candidate_ask.all_or_none):
                # This if condition is for respecting the case where candidate_ask is all-or-none
                # If the candidate_ask is all-or-none, and the incoming_bid cannot fulfill it 
                # entirely, then the candidate_ask will not be matched with the incoming_bid 
                # at all.
                transaction_size = min(remaining_order.size, candidate_ask.size)
                transactions.append(Transaction(
                    security_symbol=candidate_ask.security_symbol,
                    ask_id=candidate_ask.order_id,
                    bid_id=incoming.order_id,
                    size=transaction_size, 
                    price=candidate_ask.target_price
                ))
                incoming_bid.size -= transaction_size
                candidate_ask.size -= transaction_size
                matched_asks.append(candidate_ask)
    
    # Now that all the matchines are done, we check against the case where the incoming_bid is
    # all-or-none and/or immediate-or-cancel. Note that at this time, the incoming_bid object's
    # attributes may have been mutated, but the the corresponding record in the database has
    # not been updated to reflect the change. This is such that if the incoming bid is not
    # entirely fulfilled, then it can be reverted back to where it used to be
    remaining_bid = incoming_bid.copy()
    if incoming_bid.all_or_none and remaining_bid.size > 0:
        # If there is non-empty suborder, and the incoming bid is all-or-none, then revert
        # all changes to the incoming bid and all candidate asks. 
        # No transactions are created
        incoming_bid.revert()
        remaining_bid = incoming_bid
        for candidate_ask in matched_asks:
            candidate_ask.revert()
        transactions = []
    if incoming_bid.immediate_or_cancel and remaining_bid.size > 0:
        # If incoming bid is immediate-or-cancel, and remaining_bid is non-empty, then cancel the 
        # remaining bid
        remaining_bid.cancelled_dttm = datetime.datetime.utcnow()
    if remaining_bid.size > 0 and remaining_bid.cancelled_dttm is None:
        # If the remaining bid is not empty, then add the remaining bid to the order book
        active_orders.register(remaining_bid)
    if remaining_bid.size > 0:
        # incoming_bid abstracts the order as it comes in, so there is no need to commit it again;
        # the only thing we are concerned with here is what remains of it if the remains, after
        # counting for AON and IOC
        remaining_bid.commit()

    # Commit the transactions and clean up the order book
    for transaction in transactions:
        transaction.commit()
        matched_ask = active_orders.get(transaction.ask_id)
        active_orders.deregister(matched_ask)
        if matched_ask.size > 0:
            # If a matched ask is only partially fulfilled, then after deregistering the current
            # matched ask, create a sub-order from the remains, and register that sub-order
            remaining_ask = matched_ask.copy()
            remaining_ask.commit()
            active_orders.register(remaining_ask)
```
