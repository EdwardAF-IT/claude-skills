# Order flow

**How an order reaches shipping**

```mermaid
flowchart LR
  order[Order] --> pay[Payment]
  pay --> ship[Shipping]
  order --> ship
```

*An order ships after payment, or directly.*
