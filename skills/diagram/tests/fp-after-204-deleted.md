# Work order lookup

```mermaid
sequenceDiagram
  participant C as Client
  participant I as Internal API
  C->>I: GET /workorders/{id}
  I-->>C: 200 OK
  I-->>C: workOrderId
  I-->>C: customer
  I-->>C: year
  I-->>C: No Content
```

The lookup reads `/api/v2/workorders/{id}` and returns the order with its `Installer_ID`, its `woDetail.Customer_ID` and the
insurer name, for example Contoso.Insurance. A Lowe's order is looked up the same way.

Response example:

```
1985
```
