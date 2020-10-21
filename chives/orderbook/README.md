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

    # If no orders are matching, then the for loop below will simple be skipped;
    # in addition, because of the "orderby" above, this for-loop will begin with the lowest 
    # selling ask and iterates with increasing selling price
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
    
    # Now that all the matchines are done, we check against the case where the incoming_bid is
    # all-or-none and/or immediate-or-cancel.
    remaining_bid = Order(
        owner=incoming_bid.owner,
        security_symbol=incoming_bid.security_symbol,
        side=incoming_bid.side,
        target_price=incoming_bid.target_price,
        all_or_none=incoming_bid.all_or_none,
        immediate_or_cancel=incoming_bid.immediate_or_cancel,
        good_util_cancel=incoming_bid.good_util_cancel,
        parent_order_id=incoming_bid.order_id
    )
    if incoming_bid.all_or_none and remaining_bid.size > 0:
        # If there is non-empty suborder, and the incoming bid is all-or-none, then revert
        # all changes to the incoming bid and all candidate asks. 
        # No transactions are created
        incoming_bid.revert()
        remaining_bid = incoming_bid
        for candidate_ask in candidate_asks:
            candidate_ask.revert()
        transactions = []
    if incoming_bid.immediate_or_cancel and remaining_bid.size > 0:
        remaining_bid.cancelled_dttm = datetime.datetime.utcnow()
    if remaining_bid.size > 0 and remaining_bid.cancelled_dttm is None:
        order_book.register(remaining_bid)
    remaining_bid.commit()

    # Commit the transactions and clean up the order book
    for transaction in transactions:
        transaction.commit()
        matched_ask = active_orders.get(transaction.ask_id)
        active_orders.deregister(matched_ask)
        if matched_ask.size > 0:
            remaining_ask = Order(
                owner=matched_ask.owner,
                security_symbol=matched_ask.security_symbol,
                side=matched_ask.side,
                target_price=matched_ask.target_price,
                all_or_none=matched_ask.all_or_none,
                immediate_or_cancel=matched_ask.immediate_or_cancel,
                good_util_cancel=matched_ask.good_util_cancel,
                parent_order_id=matched_ask.order_id
            )
            remaining_ask.commit()
            active_orders.register(remaining_ask)
    


            
        
```