"""Split the nine worst IME sequence diagrams by a boundary a reader would recognise.

Every message and note is copied from the source by exact text and lands in exactly one figure
(the generator refuses otherwise). A message longer than the default 200px lifeline gap is
broken with <br/> or its path/identifier moved into a note spanning the same two participants:
the note is diagram scope, so the diff sees the detail as kept. Block keywords (alt/else/end,
rect, par, loop) are structure, not assertion, and may be re-stated where a stage is split.
Sources are copies of C:\\Code\\IME (read only); everything is written to sources/."""
import re
from pathlib import Path

import sys
# the directory holding the source .mmd files; the afters are written beside them
SRC = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).parent / "sources"
STRUCT = re.compile(r"^(alt|else|end|par|and|loop|opt|rect|critical|break|box)\b")

# ---------------------------------------------------------------- rewrites: one line -> lines
def R(*specs):
    out = {}
    for k, v in specs:
        out[k] = [v] if isinstance(v, str) else list(v)
    return out


SPECS = {}

SPECS["seq-comments-architecture"] = dict(
    prefix="Work Order Comments",
    figures=[
        ("1-external-hop", "External Hop", ["Client", "ExternalController", "ApiClientFactory", "InternalController"], [
            ("range", "Client->>ExternalController: GET /api/v2/workorders/{id}/comments", "Note over InternalController: Authorization: WorkOrderAffiliateAccessRequired"),
            ("range", "InternalController-->>ApiClientFactory: GetWorkOrderComment[] (filtered)", "ExternalController-->>Client: 200 OK + filtered comments")]),
        ("2-retrieval-and-filter", "Retrieval and Visibility Filter", ["InternalController", "RetrieveService", "Repository", "Database"], [
            ("range", "InternalController->>RetrieveService: GetCommentsAsync(request)", "Note over InternalController: FILTERING HAPPENS HERE<br/>Filter: !RestrictedForAffiliate<br/>&& !VisibleOnlyForInternalUsers")]),
    ],
    rewrite=R(
        ("Client->>ExternalController: GET /api/v2/workorders/{id}/comments", ["Client->>ExternalController: GET comments", "Note over Client,ExternalController: GET /api/v2/workorders/{id}/comments"]),
        ("Note over ExternalController: Authorization: WorkOrderBasedAccess", "Note over ExternalController: Authorization:<br/>WorkOrderBasedAccess"),
        ("ExternalController->>ApiClientFactory: Create<IImeApiWorkOrdersCommentsClient>()", ["ExternalController->>ApiClientFactory: Create typed client", "Note over ExternalController,ApiClientFactory: Create#60;IImeApiWorkOrdersCommentsClient#62;()"]),
        ("ApiClientFactory->>InternalController: HTTP GET /api/v2/workorders/{id}/comments", ["ApiClientFactory->>InternalController: HTTP GET comments", "Note over ApiClientFactory,InternalController: HTTP GET /api/v2/workorders/{id}/comments"]),
        ("Note over InternalController: Authorization: WorkOrderAffiliateAccessRequired", "Note over InternalController: Authorization:<br/>WorkOrderAffiliateAccessRequired"),
        ("RetrieveService->>Repository: GetWorkOrderCommentsAsync(workOrderId)", ["RetrieveService->>Repository: Get comments", "Note over RetrieveService,Repository: GetWorkOrderCommentsAsync(workOrderId)"]),
        ("Repository->>Database: EXEC spWorkOrderCommentsGetByWorkOrderId", ["Repository->>Database: EXEC stored procedure", "Note over Repository,Database: spWorkOrderCommentsGetByWorkOrderId"]),
        ("InternalController-->>ApiClientFactory: GetWorkOrderComment[] (filtered)", "InternalController-->>ApiClientFactory: GetWorkOrderComment[]<br/>(filtered)"),
        ("ExternalController-->>Client: 200 OK + filtered comments", "ExternalController-->>Client: 200 OK<br/>filtered comments"),
    ))

SPECS["seq-payment-history-architecture"] = dict(
    prefix="Payment History Query",
    figures=[
        ("1-request-and-records", "Request and Payment Records", ["Client", "Controller", "Service", "PaymentRepo", "Database"], [
            ("range", "Client->>Controller: GET /api/v2/payment/history/3123456", "Note over Service: Divide into on-hold vs not on-hold")]),
        ("2-on-hold-services", "On-Hold Services Check", ["Service", "ServiceRepo", "Database"], [
            ("range", "alt Has on-hold payments", "end")]),
        ("3-display-names-and-response", "Display Names and Response", ["Client", "Controller", "Service", "NinjaHelper"], [
            ("range", "Note over Service: For each payment with NinjaPaymentAmountTypeId", "Controller-->>Client: 200 OK + HistoryResponse[]")]),
    ],
    rewrite=R(
        ("Client->>Controller: GET /api/v2/payment/history/3123456", ["Client->>Controller: GET payment history", "Note over Client,Controller: GET /api/v2/payment/history/3123456"]),
        ("Note over Controller: Authorization: WorkOrderAffiliateAccessRequired", "Note over Controller: Authorization:<br/>WorkOrderAffiliateAccessRequired"),
        ("Controller->>Service: ExecuteStrictAsync(workOrderId: 3123456)", ["Controller->>Service: ExecuteStrictAsync", "Note over Controller,Service: workOrderId: 3123456"]),
        ("Service->>PaymentRepo: GetWorkOrderPaymentHistory(3123456)", ["Service->>PaymentRepo: Get payment history", "Note over Service,PaymentRepo: GetWorkOrderPaymentHistory(3123456)"]),
        ("PaymentRepo->>Database: EXEC spPaymentHistoryGetByWorkOrderId @workOrderId=3123456", ["PaymentRepo->>Database: EXEC stored procedure", "Note over PaymentRepo,Database: spPaymentHistoryGetByWorkOrderId<br/>@workOrderId=3123456"]),
        ("Note over Service: Divide into on-hold vs not on-hold", "Note over Service: Divide into on-hold<br/>vs not on-hold"),
        ("Service->>ServiceRepo: GetWorkorderServicesAsync(3123456)", ["Service->>ServiceRepo: Get services", "Note over Service,ServiceRepo: GetWorkorderServicesAsync(3123456)"]),
        ("ServiceRepo->>Database: SELECT * FROM Service WHERE WO_ID = 3123456", ["ServiceRepo->>Database: SELECT services", "Note over ServiceRepo,Database: SELECT * FROM Service<br/>WHERE WO_ID = 3123456"]),
        ("Note over Service: Check if any service NOT IN<br/>(Completed, CompletedWithoutConsent, Closed, Denied)", "Note over Service: Check if any service NOT IN<br/>(Completed,<br/>CompletedWithoutConsent,<br/>Closed, Denied)"),
        ("Note over Service: hasServiceClaim = true if any open service", "Note over Service: hasServiceClaim = true<br/>if any open service"),
        ("Note over Service: For each payment with NinjaPaymentAmountTypeId", "Note over Service: For each payment with<br/>NinjaPaymentAmountTypeId"),
        ("Service->>NinjaHelper: BuildNinjaDisplayName(prefix, amount, suffix, cardBrand)", ["Service->>NinjaHelper: Build display name", "Note over Service,NinjaHelper: BuildNinjaDisplayName(prefix,<br/>amount, suffix, cardBrand)"]),
        ("Service-->>Controller: GetPaymentHistoryByWoIdResponse[]", ["Service-->>Controller: Response[]", "Note over Controller,Service: GetPaymentHistoryByWoIdResponse[]"]),
        ("Note over Controller: Convert to HistoryResponse", "Note over Controller: Convert to<br/>HistoryResponse"),
        ("Controller-->>Client: 200 OK + HistoryResponse[]", "Controller-->>Client: 200 OK<br/>HistoryResponse[]"),
    ))

SPECS["seq-payment-confirmation"] = dict(
    prefix="Payment Confirmation",
    figures=[
        ("1-confirmation-lookup", "Confirmation Lookup", ["Client", "Controller", "Service", "PaymentRepo", "Database"], [
            ("range", "Client->>Controller: GET /api/v2/payment/confirmation?paymentIds=78901,78902", "PaymentRepo-->>Service: Payment confirmation data")]),
        ("2-payment-not-found", "Payment Not Found", ["Client", "Controller", "Service"], [
            ("range", "alt Payment not found", "Controller-->>Client: 404 Not Found"), ("lit", "end")]),
        ("3-ownership-check", "Ownership Check", ["Service", "CustomerRepo", "Database"], [
            ("lit", "alt Payment found"),
            ("range", "Service->>CustomerRepo: GetHssCustomerByWoDetailId(workOrderId)", "CustomerRepo-->>Service: Customer with Lead_Contact_Contact_ID"), ("lit", "end")]),
        ("4-outcomes", "Outcomes", ["Client", "Controller", "Service"], [
            ("range", "alt leadContactId mismatch", "Controller-->>Client: 200 OK + PaymentConfirmationResponse"), ("lit", "end")]),
    ],
    rewrite=R(
        ("Client->>Controller: GET /api/v2/payment/confirmation?paymentIds=78901,78902", ["Client->>Controller: GET confirmation", "Note over Client,Controller: GET /api/v2/payment/confirmation<br/>?paymentIds=78901,78902"]),
        ("Note over Controller: Authorization: WorkOrderAffiliateAccessRequired<br/>Extract leadContactId from JWT token", "Note over Controller: Authorization:<br/>WorkOrderAffiliateAccessRequired<br/>Extract leadContactId<br/>from JWT token"),
        ("Controller->>Service: ExecuteStrictAsync(leadContactId, paymentIds)", ["Controller->>Service: ExecuteStrictAsync", "Note over Controller,Service: (leadContactId, paymentIds)"]),
        ("Service->>PaymentRepo: GetPaymentConfirmationDetails([78901, 78902])", ["Service->>PaymentRepo: Get confirmation details", "Note over Service,PaymentRepo: GetPaymentConfirmationDetails<br/>([78901, 78902])"]),
        ("PaymentRepo->>Database: EXEC spPaymentConfirmationDetailsGet...", ["PaymentRepo->>Database: EXEC stored procedure", "Note over PaymentRepo,Database: spPaymentConfirmationDetailsGet..."]),
        ("Note over Database: STRING_SPLIT payment IDs<br/>JOIN CreditCardPayment<br/>SUM(Amount), STRING_AGG(AuthCode)<br/>EXEC spGetBalanceDue for work order", "Note over Database: STRING_SPLIT payment IDs<br/>JOIN CreditCardPayment<br/>SUM(Amount),<br/>STRING_AGG(AuthCode)<br/>EXEC spGetBalanceDue<br/>for work order"),
        ("PaymentRepo-->>Service: Payment confirmation data", "PaymentRepo-->>Service: Payment<br/>confirmation data"),
        ("Service->>CustomerRepo: GetHssCustomerByWoDetailId(workOrderId)", ["Service->>CustomerRepo: Get customer", "Note over Service,CustomerRepo: GetHssCustomerByWoDetailId<br/>(workOrderId)"]),
        ("CustomerRepo->>Database: Get customer for work order", "CustomerRepo->>Database: Get customer<br/>for work order"),
        ("CustomerRepo-->>Service: Customer with Lead_Contact_Contact_ID", "CustomerRepo-->>Service: Customer with<br/>Lead_Contact_Contact_ID"),
        ("Note over Controller: Convert to PaymentConfirmationResponse", "Note over Controller: Convert to<br/>PaymentConfirmationResponse"),
        ("Controller-->>Client: 200 OK + PaymentConfirmationResponse", "Controller-->>Client: 200 OK<br/>PaymentConfirmationResponse"),
    ))

SPECS["seq-comment-creation"] = dict(
    prefix="Work Order Comment Creation",
    figures=[
        ("1-external-hop", "External Hop and Response", ["Client", "ExternalController", "InternalController"], [
            ("range", "Client->>ExternalController: POST /api/v2/workorders/{id}/comments", "Note over InternalController: Extract currentUser.AccountId() from JWT"),
            ("range", "InternalController-->>ExternalController: 200 OK + created comment", "ExternalController-->>Client: 204 No Content"), ("lit", "end")]),
        ("2-add-comment", "Add Comment", ["InternalController", "AddService", "WorkOrderRepo", "Database"], [
            ("range", "InternalController->>AddService: AddWorkOrderCommentAsync(dto)", "AddService-->>InternalController: ServiceResult<int?>")]),
        ("3-read-back", "Read Back the Created Comment", ["InternalController", "RetrieveService", "Database"], [
            ("range", "InternalController->>RetrieveService: GetCommentsAsync(request)", "Note over InternalController: Match created comment by<br/>CommentId + AuthorAccountId")]),
    ],
    rewrite=R(
        ("Client->>ExternalController: POST /api/v2/workorders/{id}/comments", ["Client->>ExternalController: POST comment", "Note over Client,ExternalController: POST /api/v2/workorders/{id}/comments"]),
        ("Note over ExternalController: Authorization: WorkOrderBasedAccess<br/>ReturnContent header optional", "Note over ExternalController: Authorization:<br/>WorkOrderBasedAccess<br/>ReturnContent header<br/>optional"),
        ("ExternalController->>InternalController: HTTP POST, always requests content", "ExternalController->>InternalController: HTTP POST,<br/>always requests content"),
        ("Note over InternalController: Authorization: WorkOrderAffiliateAccessRequired<br/>+ RequireAccountId", "Note over InternalController: Authorization:<br/>WorkOrderAffiliateAccessRequired<br/>+ RequireAccountId"),
        ("Note over InternalController: Extract currentUser.AccountId() from JWT", "Note over InternalController: Extract<br/>currentUser.AccountId()<br/>from JWT"),
        ("InternalController->>AddService: AddWorkOrderCommentAsync(dto)", ["InternalController->>AddService: Add comment", "Note over InternalController,AddService: AddWorkOrderCommentAsync(dto)"]),
        ("Note over AddService: dto: workOrderId, comment text,<br/>accountId, srcBusinessType", "Note over AddService: dto: workOrderId,<br/>comment text,<br/>accountId,<br/>srcBusinessType"),
        ("AddService->>WorkOrderRepo: AddWorkOrderCommentAsync(...)", ["AddService->>WorkOrderRepo: Add comment", "Note over AddService,WorkOrderRepo: AddWorkOrderCommentAsync(...)"]),
        ("WorkOrderRepo->>Database: INSERT INTO WO_Comments", "WorkOrderRepo->>Database: INSERT INTO<br/>WO_Comments"),
        ("RetrieveService->>Database: Read comments for work order", "RetrieveService->>Database: Read comments<br/>for work order"),
        ("Note over InternalController: Match created comment by<br/>CommentId + AuthorAccountId", "Note over InternalController: Match created<br/>comment by CommentId<br/>+ AuthorAccountId"),
        ("InternalController-->>ExternalController: 200 OK + created comment", "InternalController-->>ExternalController: 200 OK<br/>created comment"),
        ("ExternalController-->>Client: 200 OK + created comment", "ExternalController-->>Client: 200 OK<br/>created comment"),
    ))

SPECS["seq-available-promotions"] = dict(
    prefix="Available Promotions Query",
    figures=[
        ("1-api-hop", "API Hop", ["Client", "ExternalAPI", "InternalAPI", "Service"], [
            ("range", "Client->>ExternalAPI: GET /WorkOrders/123/availablePromotions", "InternalAPI->>Service: ExecuteAsync(123)"),
            ("range", "Service-->>InternalAPI: PromotionDetailsDto[]", "ExternalAPI-->>Client: Available promotions")]),
        ("2-lookup-and-filter", "Lookup and Filter", ["Service", "WorkOrderRepo", "PromoRepo", "Database"], [
            ("range", "Service->>WorkOrderRepo: GetWoDetailByWoIdAsync(123)", "Service->>Service: Filter out IsEverydayOffer = true")]),
    ],
    rewrite=R(
        ("Client->>ExternalAPI: GET /WorkOrders/123/availablePromotions", ["Client->>ExternalAPI: GET available promotions", "Note over Client,ExternalAPI: GET /WorkOrders/123/availablePromotions"]),
        ("ExternalAPI->>ExternalAPI: Authorize (WorkOrderBasedAccess)", ["ExternalAPI->>ExternalAPI: Authorize", "Note right of ExternalAPI: WorkOrderBasedAccess"]),
        ("ExternalAPI->>InternalAPI: Proxy request with token", "ExternalAPI->>InternalAPI: Proxy request<br/>with token"),
        ("InternalAPI->>InternalAPI: Authorize (WorkOrderAffiliateAccessRequired)", ["InternalAPI->>InternalAPI: Authorize", "Note right of InternalAPI: WorkOrderAffiliateAccessRequired"]),
        ("Service->>WorkOrderRepo: GetWoDetailByWoIdAsync(123)", ["Service->>WorkOrderRepo: Get work order", "Note over Service,WorkOrderRepo: GetWoDetailByWoIdAsync(123)"]),
        ("WorkOrderRepo->>Database: SELECT HssProgramId, SrcProgramId, ServiceZip, Installer_ID", ["WorkOrderRepo->>Database: SELECT context", "Note over WorkOrderRepo,Database: SELECT HssProgramId, SrcProgramId,<br/>ServiceZip, Installer_ID"]),
        ("Service->>Service: Validate required fields", ["Service->>Service: Validate", "Note right of Service: Validate required fields"]),
        ("Service->>PromoRepo: GetAvailablePromotionsAsync(context)", ["Service->>PromoRepo: Get promotions", "Note over Service,PromoRepo: GetAvailablePromotionsAsync(context)"]),
        ("PromoRepo->>Database: SELECT Promotions WHERE date/zone/program match", ["PromoRepo->>Database: SELECT promotions", "Note over PromoRepo,Database: SELECT Promotions WHERE<br/>date/zone/program match"]),
        ("Service->>Service: Filter out IsEverydayOffer = true", ["Service->>Service: Filter", "Note right of Service: Filter out<br/>IsEverydayOffer = true"]),
        ("ExternalAPI->>ExternalAPI: Map to GetSimplePromotion", ["ExternalAPI->>ExternalAPI: Map", "Note right of ExternalAPI: Map to GetSimplePromotion"]),
    ))

CFG = ["Admin", "Wizard", "API", "Validate", "DB"]
SPECS["seq-configuration-flow"] = dict(
    prefix="Wizard Configuration",
    figures=[
        ("1-company-information", "Step 1, Company Information", CFG, [("range", "rect rgb(240, 248, 255)", "end", 1)]),
        ("2-business-settings", "Step 2, Business Settings", CFG, [("range", "rect rgb(255, 250, 240)", "end", 1)]),
        ("3-integration-settings", "Step 3, Integration Settings", CFG, [("range", "rect rgb(240, 255, 240)", "end", 3)]),
        ("4-user-and-security", "Step 4, User and Security", CFG, [("range", "rect rgb(255, 240, 245)", "end", 1)]),
        ("5-review", "Step 5, Review", ["Admin", "Wizard", "API", "DB"], [("range", "rect rgb(250, 240, 255)", "Wizard-->>Admin: Show complete review"), ("lit", "end")]),
        ("6-finalize", "Step 5, Finalize", CFG, [("lit", "rect rgb(250, 240, 255)"), ("range", "Admin->>Wizard: Confirm & finalize", "API->>DB: Mark config complete"), ("lit", "end")]),
        ("7-go-live", "Step 5, Go Live", ["Admin", "Wizard", "API", "Cache", "Event"], [("lit", "rect rgb(250, 240, 255)"), ("range", "API->>Cache: Load config into cache", "end", 1)]),
    ],
    rewrite=R(
        ("Admin->>Wizard: Start configuration wizard", "Admin->>Wizard: Start<br/>configuration wizard"),
        ("Wizard->>API: GET /api/config/wizard/status", ["Wizard->>API: GET wizard status", "Note over Wizard,API: GET /api/config/wizard/status"]),
        ("Wizard->>API: POST /api/config/wizard/step/1", ["Wizard->>API: POST step 1", "Note over Wizard,API: POST /api/config/wizard/step/1"]),
        ("Wizard->>API: POST /api/config/wizard/step/2", ["Wizard->>API: POST step 2", "Note over Wizard,API: POST /api/config/wizard/step/2"]),
        ("Wizard->>API: POST /api/config/wizard/step/3", ["Wizard->>API: POST step 3", "Note over Wizard,API: POST /api/config/wizard/step/3"]),
        ("Wizard->>API: POST /api/config/wizard/step/3?force=true", ["Wizard->>API: POST step 3, forced", "Note over Wizard,API: POST /api/config/wizard/step/3<br/>?force=true"]),
        ("Wizard->>API: POST /api/config/wizard/step/4", ["Wizard->>API: POST step 4", "Note over Wizard,API: POST /api/config/wizard/step/4"]),
        ("Wizard->>API: GET /api/config/wizard/summary", ["Wizard->>API: GET summary", "Note over Wizard,API: GET /api/config/wizard/summary"]),
        ("Wizard->>API: POST /api/config/wizard/finalize", ["Wizard->>API: POST finalize", "Note over Wizard,API: POST /api/config/wizard/finalize"]),
        ("Wizard-->>Admin: Show business settings form", "Wizard-->>Admin: Show business<br/>settings form"),
        ("Validate->>DB: Check time zone compatibility", "Validate->>DB: Check time zone<br/>compatibility"),
        ("API-->>Wizard: Warn: Some integrations offline", "API-->>Wizard: Warn: Some<br/>integrations offline"),
        ("Wizard-->>Admin: Show warnings, allow continue", "Wizard-->>Admin: Show warnings,<br/>allow continue"),
        ("API-->>Wizard: Step 3 complete (warnings)", "API-->>Wizard: Step 3 complete<br/>(warnings)"),
        ("API->>Validate: Validate security settings", "API->>Validate: Validate<br/>security settings"),
        ("API->>Event: Publish ConfigurationCompleted", "API->>Event: Publish<br/>ConfigurationCompleted"),
        ("Event->>Event: Trigger provisioning tasks:", ["Event->>Event: Trigger", "Note right of Event: Trigger provisioning tasks:"]),
    ))

SPECS["seq-credit-decision"] = dict(
    prefix="Credit Decision",
    figures=[
        ("1a-credit-pull", "Stage 1, Credit Pull and Score", ["Rep", "App", "Credit", "DB"], [
            ("range", "rect rgb(240, 248, 255)", "App->>App: Calculate risk score"), ("lit", "end")]),
        ("1b-risk-routing", "Stage 1, Risk Routing", ["Rep", "App", "Under", "DB", "Notify"], [
            ("lit", "rect rgb(240, 248, 255)"), ("range", "alt High Risk (Score < 600 or DTI > 50%)", "end", 2)]),
        ("2-underwriting-review", "Stage 2, Underwriting Review", ["Rep", "App", "Under", "DB", "Notify"], [
            ("range", "rect rgb(255, 250, 240)", "end", 2)]),
        ("3a-escalation-and-review", "Stage 3, Escalation and Manager Review", ["Under", "App", "Mgr", "DB", "Notify"], [
            ("range", "rect rgb(240, 255, 240)", "Mgr->>Mgr: Evaluate:"), ("lit", "end")]),
        ("3b-manager-decision", "Stage 3, Manager Decision", ["Mgr", "App", "DB", "Notify"], [
            ("lit", "rect rgb(240, 255, 240)"), ("lit", "alt Manager Approves Exception"),
            ("range", "Mgr->>App: Decision: Approve", "App->>Notify: Notify underwriter + rep"),
            ("lit", "else Manager Denies Exception"),
            ("range", "Mgr->>App: Decision: Uphold decline", "App->>Notify: Send final decline"),
            ("lit", "end"), ("lit", "end")]),
        ("3c-who-is-told", "Stage 3, Who Is Told", ["Rep", "Under", "Notify"], [
            ("lit", "rect rgb(240, 255, 240)"), ("lit", "alt Manager Approves Exception"),
            ("range", "Notify-->>Under: Manager approved exception", "Notify-->>Rep: Application approved (conditions)"),
            ("lit", "else Manager Denies Exception"),
            ("range", "Notify-->>Rep: Final decline notification", "Notify-->>Rep: Final decline notification"),
            ("lit", "end"), ("lit", "end")]),
        ("4-lender-submission", "Stage 4, Lender Submission", ["Rep", "App", "Lender", "DB", "Notify"], [
            ("range", "rect rgb(255, 240, 245)", "end", 1)]),
    ],
    rewrite=R(
        ("Rep->>App: Submit customer application<br/>(SSN, DOB, income, amount)", ["Rep->>App: Submit customer<br/>application", "Note over Rep,App: (SSN, DOB, income, amount)"]),
        ("App->>DB: Save application (Status: Pending)", ["App->>DB: Save application", "Note over App,DB: Status: Pending"]),
        ("DB-->>App: Returns new application id...", "DB-->>App: Returns new<br/>application id..."),
        ("App->>Credit: Request hard credit pull", "App->>Credit: Request hard<br/>credit pull"),
        ("App->>DB: Update status: Auto-Declined", "App->>DB: Update status:<br/>Auto-Declined"),
        ("App->>Notify: Send decline notification", "App->>Notify: Send decline<br/>notification"),
        ("Notify-->>Rep: Email: Application declined", "Notify-->>Rep: Email:<br/>Application declined"),
        ("App->>DB: Update status: Manual Review", "App->>DB: Update status:<br/>Manual Review"),
        ("Notify-->>Under: Email: New application for review", "Notify-->>Under: Email: New application<br/>for review"),
        ("App->>DB: Update status: Auto-Approved (Stage 1)", "App->>DB: Update status:<br/>Auto-Approved (Stage 1)"),
        ("Note over App: Proceed directly to lender submission", "Note over App: Proceed directly to<br/>lender submission"),
        ("Under->>App: Review application FA-12345", "Under->>App: Review application<br/>FA-12345"),
        ("App->>DB: Fetch application + credit data", "App->>DB: Fetch application<br/>+ credit data"),
        ("App-->>Under: Display full application", "App-->>Under: Display full<br/>application"),
        ("Under->>App: Decision: Conditional Approval", "Under->>App: Decision:<br/>Conditional Approval"),
        ("App->>DB: Update status: Conditional Approval", "App->>DB: Update status:<br/>Conditional Approval"),
        ("App->>Notify: Request docs from customer", "App->>Notify: Request docs<br/>from customer"),
        ("Notify-->>Rep: Email: Additional docs needed", "Notify-->>Rep: Email: Additional<br/>docs needed"),
        ("App->>Under: Notify: Documents received", "App->>Under: Notify:<br/>Documents received"),
        ("Under->>App: Decision: Approve (conditions met)", "Under->>App: Decision: Approve<br/>(conditions met)"),
        ("App->>DB: Update status: Info Requested", "App->>DB: Update status:<br/>Info Requested"),
        ("Notify-->>Rep: Email: Info request sent", "Notify-->>Rep: Email:<br/>Info request sent"),
        ("App->>DB: Update status: Declined (Underwriter)", "App->>DB: Update status:<br/>Declined (Underwriter)"),
        ("App->>Notify: Send decline with reason", "App->>Notify: Send decline<br/>with reason"),
        ("App->>DB: Update status: Manager Review", "App->>DB: Update status:<br/>Manager Review"),
        ("Notify-->>Mgr: Email: Manager approval needed", "Notify-->>Mgr: Email: Manager<br/>approval needed"),
        ("Mgr->>App: Review application + underwriter notes", "Mgr->>App: Review application<br/>+ underwriter notes"),
        ("App->>DB: Update status: Manager Approved (Exception)", "App->>DB: Update status:<br/>Manager Approved<br/>(Exception)"),
        ("App->>DB: Log exception reason + manager ID", "App->>DB: Log exception reason<br/>+ manager ID"),
        ("App->>Notify: Notify underwriter + rep", "App->>Notify: Notify<br/>underwriter + rep"),
        ("Notify-->>Under: Manager approved exception", "Notify-->>Under: Manager approved<br/>exception"),
        ("Notify-->>Rep: Application approved (conditions)", "Notify-->>Rep: Application approved<br/>(conditions)"),
        ("Mgr->>App: Decision: Uphold decline", "Mgr->>App: Decision:<br/>Uphold decline"),
        ("App->>DB: Update status: Declined (Final)", "App->>DB: Update status:<br/>Declined (Final)"),
        ("Notify-->>Rep: Final decline notification", "Notify-->>Rep: Final decline<br/>notification"),
        ("App->>Lender: Submit approved application<br/>to Aqua Finance", "App->>Lender: Submit approved<br/>application<br/>to Aqua Finance"),
        ("Lender-->>App: Lender decision: Approved", "Lender-->>App: Lender decision:<br/>Approved"),
        ("App->>DB: Update status: Lender Approved", "App->>DB: Update status:<br/>Lender Approved"),
        ("App->>Notify: Send approval to customer", "App->>Notify: Send approval<br/>to customer"),
        ("Notify-->>Rep: Schedule signing appointment", "Notify-->>Rep: Schedule signing<br/>appointment"),
        ("App->>DB: Update status: Ready for Signature", "App->>DB: Update status:<br/>Ready for Signature"),
    ))

PQ = ["User", "UI", "API", "Cache", "DB"]
SPECS["seq-payment-queries"] = dict(
    prefix="Payment History Queries",
    figures=[
        ("1-recent-payments", "Recent Payments", PQ, [("range", "rect rgb(240, 248, 255)", "end", 2)]),
        ("2-customer-payments", "Customer Payments", PQ, [("range", "rect rgb(255, 250, 240)", "end", 1)]),
        ("3-multi-criteria", "Multi-Criteria Filters", PQ, [("range", "rect rgb(240, 255, 240)", "end", 1)]),
        ("4-full-text-search", "Full-Text Search", ["User", "UI", "API", "Index", "DB"], [("range", "rect rgb(255, 240, 245)", "end", 2)]),
        ("5-export", "Export", ["User", "UI", "API", "DB"], [("range", "rect rgb(250, 240, 255)", "end", 2)]),
    ],
    rewrite=R(
        ("UI->>API: GET /api/payments?limit=50", ["UI->>API: GET payments", "Note over UI,API: GET /api/payments?limit=50"]),
        ("API->>Cache: Check cache key: payments:recent:50", ["API->>Cache: Check cache key", "Note over API,Cache: payments:recent:50"]),
        ("API-->>UI: Return payments (200 OK)", "API-->>UI: Return payments<br/>(200 OK)"),
        ("UI-->>User: Display recent payments", "UI-->>User: Display<br/>recent payments"),
        ("User->>UI: Search: Customer ID C-12345", "User->>UI: Search:<br/>Customer ID C-12345"),
        ("UI->>API: GET /api/payments?customerId=C-12345&limit=100", ["UI->>API: GET customer payments", "Note over UI,API: GET /api/payments<br/>?customerId=C-12345&limit=100"]),
        ("API->>Cache: Check cache: payments:customer:C-12345", ["API->>Cache: Check cache", "Note over API,Cache: payments:customer:C-12345"]),
        ("Cache-->>API: Cache miss (customer-specific)", "Cache-->>API: Cache miss<br/>(customer-specific)"),
        ("API-->>UI: Return payments + summary", "API-->>UI: Return payments<br/>+ summary"),
        ("API->>Cache: Check complex query cache", "API->>Cache: Check complex<br/>query cache"),
        ("Cache-->>API: Cache miss (unique query)", "Cache-->>API: Cache miss<br/>(unique query)"),
        ("DB-->>API: Return 25 payments (page 1)", "DB-->>API: Return 25 payments<br/>(page 1)"),
        ("API->>DB: SELECT COUNT(*) FROM payments<br/>WHERE ... (same filters)", "API->>DB: SELECT COUNT(*)<br/>FROM payments<br/>WHERE ... (same filters)"),
        ("DB-->>API: Total count: 147 matching", "DB-->>API: Total count:<br/>147 matching"),
        ("UI-->>User: Display results with pagination", "UI-->>User: Display results<br/>with pagination"),
        ("API->>DB: SELECT ... LIMIT 25 OFFSET 25", "API->>DB: SELECT ...<br/>LIMIT 25 OFFSET 25"),
        ('User->>UI: Search: "invoice 2024-INV-1234"', 'User->>UI: Search:<br/>"invoice 2024-INV-1234"'),
        ("UI->>API: GET /api/payments/search?q=invoice+2024-INV-1234", ["UI->>API: GET search", "Note over UI,API: GET /api/payments/search<br/>?q=invoice+2024-INV-1234"]),
        ("Index-->>API: Return matching payment IDs", "Index-->>API: Return matching<br/>payment IDs"),
        ("DB-->>API: Return full payment records", "DB-->>API: Return full<br/>payment records"),
        ("UI-->>User: Display matching payments", "UI-->>User: Display<br/>matching payments"),
        ("User->>UI: Export to CSV (500+ records)", "User->>UI: Export to CSV<br/>(500+ records)"),
        ("UI->>API: POST /api/payments/export", ["UI->>API: POST export", "Note over UI,API: POST /api/payments/export"]),
        ("API->>API: Validate: Max 10,000 records", ["API->>API: Validate", "Note right of API: Max 10,000 records"]),
        ("API->>DB: Stream query results<br/>(cursor-based pagination)", "API->>DB: Stream query results<br/>(cursor-based<br/>pagination)"),
        ("API->>API: Generate download URL<br/>(S3/Blob Storage, 1-hour expiry)", ["API->>API: Generate download URL", "Note right of API: S3/Blob Storage,<br/>1-hour expiry"]),
    ))

SPECS["seq-price-calculation"] = dict(
    prefix="Price Calculation",
    figures=[
        ("1a-tiered-rule-validate", "Tiered Rule, Validate", ["Admin", "UI", "API", "Rules"], [
            ("range", "rect rgb(240, 248, 255)", "Rules-->>API: Validation result"), ("lit", "end")]),
        ("1b-tiered-rule-persist", "Tiered Rule, Persist and Publish", ["API", "DB", "Cache", "Event"], [
            ("lit", "rect rgb(240, 248, 255)"), ("lit", "alt Valid Rule"),
            ("range", "API->>DB: Save pricing rule", "Event-->>API: Event logged"), ("lit", "end"), ("lit", "end")]),
        ("1c-tiered-rule-outcome", "Tiered Rule, Outcome", ["Admin", "UI", "API"], [
            ("lit", "rect rgb(240, 248, 255)"), ("lit", "alt Valid Rule"),
            ("range", "API-->>UI: Success: Rule created", "UI-->>Admin: Show confirmation"),
            ("lit", "else Invalid Rule"),
            ("range", "API-->>UI: Error: Overlapping tiers", "UI-->>Admin: Show error message"), ("lit", "end"), ("lit", "end")]),
        ("2a-discount-validate", "Volume Discount, Validate", ["Admin", "UI", "API", "Rules", "DB"], [
            ("range", "rect rgb(255, 250, 240)", "Rules-->>API: Valid"), ("lit", "end")]),
        ("2b-discount-persist", "Volume Discount, Persist and Publish", ["API", "DB", "Cache", "Event"], [
            ("lit", "rect rgb(255, 250, 240)"), ("range", "API->>DB: Save discount rule", "Event-->>API: Event logged"), ("lit", "end")]),
        ("2c-discount-outcome", "Volume Discount, Outcome", ["Admin", "UI", "API"], [
            ("lit", "rect rgb(255, 250, 240)"), ("range", "API-->>UI: Success: Discount active", "UI-->>Admin: Show confirmation"), ("lit", "end")]),
        ("3a-view-stacking", "Rule Priority, View Stacking", ["Admin", "UI", "API", "Rules"], [
            ("range", "rect rgb(240, 255, 240)", "UI-->>Admin: Display stacking order"), ("lit", "end")]),
        ("3b-modify-priority", "Rule Priority, Modify", ["Admin", "UI", "API", "DB"], [
            ("lit", "rect rgb(240, 255, 240)"), ("range", "Admin->>UI: Modify priority", "DB-->>API: Updated"), ("lit", "end")]),
        ("3c-priority-cache-and-event", "Rule Priority, Cache, Event and Confirmation", ["Admin", "UI", "API", "Cache", "Event"], [
            ("lit", "rect rgb(240, 255, 240)"), ("range", "API->>Cache: Clear all pricing cache", "end", 1)]),
        ("4-test-calculation", "Test Pricing Calculation", ["Admin", "UI", "API", "Rules", "DB"], [
            ("range", "rect rgb(255, 240, 245)", "end", 1)]),
    ],
    rewrite=R(
        ("UI->>API: POST /api/pricing/rules", ["UI->>API: POST rule", "Note over UI,API: POST /api/pricing/rules"]),
        ("DB-->>API: Returns new rule id...", "DB-->>API: Returns new<br/>rule id..."),
        ("API->>Cache: Invalidate affected products", "API->>Cache: Invalidate<br/>affected products"),
        ("API->>Event: Publish PricingRuleCreated", "API->>Event: Publish<br/>PricingRuleCreated"),
        ("API-->>UI: Error: Overlapping tiers", "API-->>UI: Error:<br/>Overlapping tiers"),
        ("UI->>API: POST /api/pricing/discounts", ["UI->>API: POST discount", "Note over UI,API: POST /api/pricing/discounts"]),
        ("DB-->>API: Returns new discount id...", "DB-->>API: Returns new<br/>discount id..."),
        ("API->>Cache: Clear category pricing cache", "API->>Cache: Clear category<br/>pricing cache"),
        ("API->>Event: Publish DiscountRuleCreated", "API->>Event: Publish<br/>DiscountRuleCreated"),
        ("API-->>UI: Success: Discount active", "API-->>UI: Success:<br/>Discount active"),
        ("UI->>API: GET /api/pricing/rules?stacking", ["UI->>API: GET stacking", "Note over UI,API: GET /api/pricing/rules?stacking"]),
        ("API->>Rules: Get stacking configuration", "API->>Rules: Get stacking<br/>configuration"),
        ("UI->>API: PUT /api/pricing/rules/priority", ["UI->>API: PUT priority", "Note over UI,API: PUT /api/pricing/rules/priority"]),
        ("API->>Event: Publish PricingPriorityChanged", "API->>Event: Publish<br/>PricingPriorityChanged"),
        ("UI->>API: POST /api/pricing/calculate/test", ["UI->>API: POST test calculation", "Note over UI,API: POST /api/pricing/calculate/test"]),
        ("API->>Rules: Calculate with all rules", "API->>Rules: Calculate<br/>with all rules"),
        ("API-->>UI: Return detailed breakdown", "API-->>UI: Return detailed<br/>breakdown"),
    ))


# ---------------------------------------------------------------- the generator
def body_lines(src: str):
    lines = src.splitlines()
    i = next(n for n, ln in enumerate(lines) if ln.strip().startswith("sequenceDiagram"))
    parts, body = {}, []
    for ln in lines[i + 1:]:
        s = ln.strip()
        if not s or s.startswith("%%") or s == "autonumber":
            continue
        m = re.match(r"(participant|actor)\s+(\S+)(.*)$", s)
        if m:
            parts[m.group(2)] = s
            continue
        body.append(s)
    return parts, body


def note_span(line: str, present: list[str]) -> str:
    m = re.match(r"(Note over )(\S+?),(\S+?)(: .*)$", line)
    if not m:
        return line
    a, b = m.group(2), m.group(3)
    if a not in present:
        a = present[0]
    if b not in present:
        b = present[-1]
    return f"{m.group(1)}{a},{b}{m.group(4)}"


# Measured on the renders: a message line over ~18 characters widens the 200px lifeline gap
# and a five-participant figure drops under the 7pt floor; a note over two neighbours has
# ~330px, a note over one actor 130px, an actor box 130px. Text is only re-broken, never
# reworded: <br/> is a space to the fidelity gate.
MSG_CHARS, SPAN_CHARS, BOX_CHARS = 18, 30, 18


def camel_chunks(word: str) -> list[str]:
    # seams: a capital after a lower-case letter, or an underscore (kept with the piece before)
    return re.findall(r"[A-Z]+(?![a-z])_*|[A-Z]?[a-z0-9]+_*|[^A-Za-z0-9]+", word) or [word]


def pack(words: list[str], limit: int) -> list[str]:
    lines, line = [], ""
    for w in words:
        if line and len(line) + 1 + len(w) > limit:
            lines.append(line); line = w
        else:
            line = (line + " " + w).strip()
    if line:
        lines.append(line)
    return lines


def wrap(text: str, limit: int, break_words: bool = True) -> str:
    out = []
    for part in text.split("<br/>"):
        words = []
        for w in part.split(" "):
            # only a bare identifier is broken at its seams; a path or query stays whole
            if break_words and len(w) > limit + 2 and re.search(r"[a-z][A-Z]|_", w) and re.fullmatch(r"[\w()\[\].,:]+", w):
                # a long identifier is broken at its camel-case seams into lines that fit
                pieces, cur = [], ""
                for c in camel_chunks(w):
                    if cur and len(cur) + len(c) > limit + 2:
                        pieces.append(cur); cur = c
                    else:
                        cur += c
                if cur:
                    pieces.append(cur)
                words.extend(pieces if len(pieces) > 1 else [w])
                if len(pieces) > 1:
                    # each piece must start its own line: mark with a sentinel
                    words = words[:-len(pieces)] + [p + "\x00" for p in pieces]
            else:
                words.append(w)
        # sentinel words force a break after them
        lines, line = [], ""
        for w in words:
            forced = w.endswith("\x00")
            w = w.rstrip("\x00")
            if line and (len(line) + 1 + len(w) > limit or line.endswith("\x01")):
                lines.append(line.rstrip("\x01")); line = w
            else:
                line = (line.rstrip("\x01") + " " + w).strip()
            if forced:
                line += "\x01"
        if line:
            lines.append(line.rstrip("\x01"))
        out.extend(lines)
    return "<br/>".join(out)


def fit(line: str, pids: list[str]) -> str:
    """Re-break one figure line so it fits the default geometry."""
    m = re.match(r"^(\S+?\s*(?:-->>|->>|-x|--x|-\)|--\))\s*\S+?\s*:\s*)(.*)$", line)
    if m:
        return m.group(1) + wrap(m.group(2), MSG_CHARS)
    m = re.match(r"^(participant|actor)\s+(\S+)\s+as\s+(.*)$", line)
    if m:
        return f"{m.group(1)} {m.group(2)} as " + wrap(m.group(3), BOX_CHARS)
    m = re.match(r"^Note over (\S+?),(\S+?): (.*)$", line)
    if m:
        return f"Note over {m.group(1)},{m.group(2)}: " + wrap(m.group(3), SPAN_CHARS)
    m = re.match(r"^Note (over|right of|left of) (\S+?): (.*)$", line)
    if m:
        who, text = m.group(2), m.group(3)
        # a note beside an outer actor hangs outside the figure and widens it; over the actor
        # it sits inside the slot the actor already has
        m = re.match(r"^Note (over) (\S+?): (.*)$", f"Note over {who}: {text}")
        longest = max(len(w) for part in text.split("<br/>") for w in part.split(" "))
        if longest > BOX_CHARS and who in pids:
            # a word no single-actor note can hold: span the neighbour instead of widening the slot
            i = pids.index(who)
            a, b = (pids[i], pids[i + 1]) if i + 1 < len(pids) else (pids[i - 1], pids[i])
            return f"Note over {a},{b}: " + wrap(text, SPAN_CHARS)
        return f"Note {m.group(1)} {who}: " + wrap(text, BOX_CHARS)
    return line


def generate(name: str, spec: dict) -> list[str]:
    src = (SRC / f"{name}.mmd").read_text(encoding="utf-8")
    parts, body = body_lines(src)
    consumed = [False] * len(body)
    written = []
    for n, (slug, subtitle, pids, items) in enumerate(spec["figures"], 1):
        out = ["---", f"title: {spec['prefix']} {n} of {len(spec['figures'])} - {subtitle}", "---", "sequenceDiagram"]
        out += ["    " + fit(parts[p], pids) for p in pids]
        for item in items:
            if item[0] == "lit":
                out.append("    " + item[1])
                continue
            _, start, end, *rest = item
            nth = rest[0] if rest else 1
            i = next((k for k, s in enumerate(body) if s == start and not consumed[k]), None)
            assert i is not None, f"{name}: start not found or already used: {start}"
            j, seen = None, 0
            for k in range(i, len(body)):
                if body[k] == end and (k > i or start == end):
                    seen += 1
                    if seen == nth:
                        j = k
                        break
            if start == end:
                j = i
            assert j is not None, f"{name}: end not found: {end}"
            for k in range(i, j + 1):
                s = body[k]
                if not STRUCT.match(s):
                    assert not consumed[k], f"{name}: line used twice: {s}"
                    consumed[k] = True
                for ln in spec["rewrite"].get(s, [s]):
                    out.append("    " + fit(note_span(ln, pids), pids))
        # every participant a message or note names must be declared in this figure
        for ln in out[4:]:
            for pid in re.findall(r"^\s*(\S+?)\s*(?:-->>|->>|-x|--x|-\)|--\))", ln) + re.findall(r"(?:-->>|->>|-x|--x|-\)|--\))\s*(\S+?)\s*:", ln) + re.findall(r"Note (?:over|right of|left of) ([^:]+):", ln):
                for p in re.split(r",\s*", pid):
                    assert p in pids, f"{name}/{slug}: {p!r} used but not declared ({ln.strip()})"
        path = SRC / f"{name}-after-{slug}.mmd"
        path.write_text("\n".join(out) + "\n", encoding="utf-8")
        written.append(path.name)
    missing = [s for s, c in zip(body, consumed) if not c and not STRUCT.match(s)]
    assert not missing, f"{name}: lines not placed: {missing}"
    return written


if __name__ == "__main__":
    rows = []
    for name, spec in SPECS.items():
        files = generate(name, spec)
        print(f"{name}: {len(files)} figures, every line placed once")
        rows.append(f'    "{name} (split x{len(files)})": ("{name}.mmd", {files!r}),\n')
    r = SRC.parent / "rerun.py"
    t = r.read_text(encoding="utf-8") if r.exists() else ""
    if t and "seq-comments-architecture (split" not in t:
        anchor = '    "class-error-response (envelope + table, identifier deleted)"'
        t = t.replace(anchor, "".join(rows) + anchor, 1)
        r.write_text(t, encoding="utf-8")
        print("rows registered")
