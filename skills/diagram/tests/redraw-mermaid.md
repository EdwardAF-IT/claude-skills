# Order flow

```mermaid
flowchart LR
  order[Order] --> pay[Payment]
  pay --> ship[Shipping]
  order --> ship
```
