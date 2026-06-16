/**
 * Typed shapes for the Hearth API contract (docs/api/contract-v0.md).
 * snake_case is preserved on the wire; we keep it on the types so the client is
 * a 1:1 mirror of the contract and there's no hidden casing transform to drift.
 */

/** §1.1 — success envelope. `meta` is `null` for single-resource responses. */
export interface PageMeta {
  next_cursor: string | null;
  limit: number;
  total: number | null;
}

export interface Envelope<T> {
  data: T;
  meta: PageMeta | null;
}

/** §1.2 — canonical error body. `code` is a closed set in the contract. */
export type ErrorCode =
  | "validation_error"
  | "unauthenticated"
  | "forbidden"
  | "not_found"
  | "conflict"
  | "cart_already_open"
  | "duplicate_review"
  | "email_taken"
  | "out_of_stock"
  | "return_window_closed"
  | "empty_cart"
  | "payment_declined"
  | "rate_limited"
  | "internal_error"
  | "not_implemented";

export interface ErrorBody {
  code: ErrorCode;
  message: string;
  details: unknown | null;
}

export interface ErrorEnvelope {
  error: ErrorBody;
}

/** auth — §2. Roles per the ORM/journeys. */
export type UserRole = "buyer" | "seller" | "support" | "admin";

export interface UserOut {
  id: string;
  email: string;
  display_name: string;
  role: UserRole;
  /** Live `UserOut` carries `is_active` (Day-22 flip); there is no `email_verified`. */
  is_active: boolean;
  created_at: string;
}

/** `SessionOut` — returned by register/login; carries the opaque bearer token. */
export interface SessionOut {
  token: string;
  expires_at: string;
  user: UserOut;
}

export interface LogoutResult {
  revoked: boolean;
}

/** Request bodies — `extra="forbid"` server-side, so keep these exact. */
export interface RegisterRequest {
  email: string;
  password: string;
  display_name: string;
  role: Extract<UserRole, "buyer" | "seller">;
}

export interface LoginRequest {
  email: string;
  password: string;
}

/* ------------------------------------------------------------------ *
 * search — §search. `GET /search?q=` → `SearchResult[]` inside the
 * standard `{ data, meta }` envelope; `meta.mode` ∈ keyword|semantic|hybrid.
 * ------------------------------------------------------------------ */

export type SearchMode = "keyword" | "semantic" | "hybrid";

/** Stock state on a listing — drives the in-stock / low / OOS badges. */
export type StockState = "in_stock" | "low_stock" | "out_of_stock";

export interface SearchResult {
  id: string;
  slug: string;
  title: string;
  maker: string;
  /** Price in minor units (cents) — formatted client-side, never on the wire. */
  price_cents: number;
  currency: string;
  stock: StockState;
  /** Optional alt text for a real product image; null → token placeholder. */
  image_alt: string | null;
  /** True when this row was surfaced by the concierge (★ Picked in the grid). */
  picked?: boolean;
}

/** `meta` shape for a search response — extends the page meta with retrieval mode. */
export interface SearchMeta extends PageMeta {
  mode: SearchMode;
}

/* ------------------------------------------------------------------ *
 * product — §catalog `GET /products/{id}` → `ProductDetail`.
 * ------------------------------------------------------------------ */

export interface ProductImage {
  id: string;
  /** Meaningful image → alt text (a11y A8). */
  alt: string;
  /** Placeholder tone token while the real asset pipeline is not wired. */
  tone?: string;
}

export interface ProductVariant {
  id: string;
  /** e.g. "Glaze", "Size" — the option dimension. */
  option_name: string;
  /** e.g. "Deep moss", "Large · 28cm". */
  option_value: string;
  stock: StockState;
}

export interface ProductDetail {
  id: string;
  slug: string;
  title: string;
  maker: string;
  maker_location: string | null;
  price_cents: number;
  currency: string;
  stock: StockState;
  description: string;
  rating: number | null;
  review_count: number;
  images: ProductImage[];
  variants: ProductVariant[];
}

/* ------------------------------------------------------------------ *
 * cart — §cart. Shapes mirror `app/schemas/cart.py` (CamelModel keeps
 * snake_case on the wire): `CartItemAdd` / `CartItemUpdate` / `CartItemOut`
 * / `CartOut`. Money is minor units (`*_minor`), qty is `qty`.
 * ------------------------------------------------------------------ */

export type CartStatus = "open" | "converted" | "abandoned";

/** `POST /cart/items` — add (or increment) a variant in the open cart. */
export interface CartItemAdd {
  variant_id: string;
  qty: number;
}

/** `PATCH /cart/items/{id}` — set absolute line quantity (>0). */
export interface CartItemUpdate {
  qty: number;
}

/** A cart line with denormalized display fields + live stock signal. */
export interface CartItemOut {
  id: string;
  variant_id: string;
  product_id: string;
  title: string;
  sku: string;
  options: Record<string, unknown>;
  unit_price_minor: number;
  currency: string;
  qty: number;
  line_total_minor: number;
  in_stock: boolean;
  added_at: string;
  /** Display-only: the variant option value (e.g. "Deep moss"). Convenience. */
  option_value?: string;
  /** Product slug for the line's deep-link to the PDP. */
  slug?: string;
}

export interface CartOut {
  id: string;
  status: CartStatus;
  items: CartItemOut[];
  subtotal_minor: number;
  currency: string;
  item_count: number;
  updated_at: string;
}

/* ------------------------------------------------------------------ *
 * orders + test-mode payments — §orders. Mirrors `app/schemas/order.py`.
 * Single multi-store order with frozen per-item snapshots; two-step
 * test-mode payment (intent → confirm) with the deterministic decline.
 * ------------------------------------------------------------------ */

export type OrderStatus =
  | "placed"
  | "packed"
  | "shipped"
  | "delivered"
  | "cancelled";

export type FulfilStatus = "pending" | "fulfilled" | "cancelled";

export type PaymentStatus =
  | "pending"
  | "authorized"
  | "captured"
  | "failed"
  | "refunded";

/** A shipping address — `AddressIn` on the wire. */
export interface AddressIn {
  name: string;
  line1: string;
  line2?: string | null;
  city: string;
  region: string;
  postal_code: string;
  country: string;
}

/** `POST /orders` — convert the open cart to an order (idempotent). */
export interface CheckoutRequest {
  ship_address: AddressIn;
  idempotency_key?: string | null;
}

/** A frozen order line (snapshot fields are immutable post-checkout). */
export interface OrderItemOut {
  id: string;
  variant_id: string | null;
  title_snapshot: string;
  options_snapshot: Record<string, unknown>;
  store_name_snapshot: string;
  unit_price_minor: number;
  qty: number;
  fulfil_status: FulfilStatus;
  /** Display-only: product slug so the line deep-links to its PDP. */
  slug?: string;
}

/** A test-mode payment record. */
export interface PaymentOut {
  id: string;
  status: PaymentStatus;
  provider_ref: string | null;
  amount_minor: number;
  currency: string;
  created_at: string;
}

/** `POST /orders/{id}/payment-intent` — the mock intent the client confirms. */
export interface PaymentIntentOut {
  payment_id: string;
  client_secret: string;
  status: PaymentStatus;
  amount_minor: number;
  currency: string;
}

/** `POST /orders/{id}/payment-confirm` — `outcome` drives success vs decline. */
export interface PaymentConfirmRequest {
  payment_id: string;
  outcome: Extract<PaymentStatus, "captured" | "failed">;
}

/** Order as shown in the "my orders" list. */
export interface OrderSummary {
  id: string;
  order_number: string;
  status: OrderStatus;
  total_minor: number;
  currency: string;
  item_count: number;
  placed_at: string;
}

/** Full order detail + the status-timeline source. */
export interface OrderDetail extends OrderSummary {
  subtotal_minor: number;
  shipping_minor: number;
  tax_minor: number;
  ship_address: Record<string, unknown> | null;
  items: OrderItemOut[];
  payments: PaymentOut[];
  updated_at: string;
  /** Display-only: whether this order is within the return window. */
  return_eligible?: boolean;
}

/* ------------------------------------------------------------------ *
 * returns — §returns. Mirrors `app/schemas/returns.py`. A return made
 * outside the window via the agent lands in `hitl_pending` (the HITL path).
 * ------------------------------------------------------------------ */

export type ReturnStatus =
  | "requested"
  | "approved"
  | "rejected"
  | "hitl_pending"
  | "refunded";

export type ReturnReason =
  | "damaged"
  | "not_as_described"
  | "wrong_item"
  | "no_longer_needed"
  | "arrived_late"
  | "other";

export interface ReturnItemRequest {
  order_item_id: string;
  qty: number;
}

/** `POST /orders/{id}/returns` — request a return. */
export interface ReturnCreate {
  reason_code: ReturnReason;
  note?: string | null;
  items: ReturnItemRequest[];
}

export interface ReturnItemOut {
  id: string;
  order_item_id: string;
  qty: number;
}

/** A return with status (incl. `hitl_pending` for the HITL path). */
export interface ReturnOut {
  id: string;
  order_id: string;
  status: ReturnStatus;
  reason_code: ReturnReason;
  note: string | null;
  within_window: boolean;
  approved_by: string | null;
  items: ReturnItemOut[];
  created_at: string;
  resolved_at: string | null;
}

/* ------------------------------------------------------------------ *
 * seller — §seller. Mirrors `app/schemas/seller.py`. The maker dashboard:
 * orders to fulfil, the agent-generated merchandising nudges, fulfilment.
 * ------------------------------------------------------------------ */

export type StoreStatus = "draft" | "active" | "suspended";

/** A merchandising/pricing nudge (agent-generated, grounded in catalog data). */
export interface NudgeOut {
  id: string;
  product_id: string;
  headline: string;
  reason: string;
  suggested_change: Record<string, unknown>;
  /** Display-only: product slug + title so the nudge references a real listing. */
  slug?: string;
  product_title?: string;
  /** Display-only: set true once accepted (audited, reversible). */
  accepted?: boolean;
}

/** `POST /seller/nudges/{id}/accept` — apply the nudge (audited, reversible). */
export interface NudgeAcceptRequest {
  idempotency_key?: string | null;
}

/** `PATCH /seller/order-items/{id}/fulfil` — mark a line fulfilled/cancelled. */
export interface FulfilRequest {
  fulfil_status: FulfilStatus;
}

/** Display-only inventory snapshot row for the seller listings table. */
export interface SellerListing {
  product_id: string;
  slug: string;
  title: string;
  status: StoreStatus;
  price_minor: number;
  currency: string;
  qty_on_hand: number;
  stock: StockState;
}

/** Display-only: the seller dashboard's aggregate snapshot. */
export interface SellerDashboard {
  store_name: string;
  listings: SellerListing[];
  orders: OrderSummary[];
  order_items: SellerFulfilItem[];
  nudges: NudgeOut[];
}

/** A single order line awaiting fulfilment, for the seller's fulfil table. */
export interface SellerFulfilItem {
  id: string;
  order_number: string;
  title_snapshot: string;
  options_snapshot: Record<string, unknown>;
  qty: number;
  unit_price_minor: number;
  currency: string;
  fulfil_status: FulfilStatus;
}

/* ------------------------------------------------------------------ *
 * agent — Ember. The assistant turn is an SSE stream (ADR-0021):
 * ordered `token → citations → done` frames (`error` is terminal).
 * These mirror the typed payloads in `app/schemas/agent.py`.
 * ------------------------------------------------------------------ */

export type AgentSurface = "buyer" | "support" | "seller";

/** `token` frame payload — a chunk of the assistant message. Append in order. */
export interface TokenEvent {
  delta: string;
}

export type CitationSourceType = "product" | "policy" | "store" | "review";

export interface Citation {
  source_type: CitationSourceType;
  source_id: string;
  chunk_index: number;
  snippet: string;
  score: number;
}

/** `citations` frame payload. */
export interface CitationsEvent {
  citations: Citation[];
}

/** A grounded generative product card carried on the terminal `done` frame. */
export interface AgentRecommendation {
  product_id: string;
  slug: string;
  title: string;
  maker: string;
  price_cents: number;
  currency: string;
  stock: StockState;
  /** The defensible "why" (J-BUY-02) rendered as `agent-recommendation-reason`. */
  reason: string;
  image_alt: string | null;
}

/** The action the turn took; `outcome` null for pure clarify/refusal. */
export type AgentActionKind =
  | "recommend"
  | "clarify"
  | "refuse"
  | "add_to_cart"
  | "checkout"
  | "return"
  | null;

export type AgentOutcome = "applied" | "refused" | "hitl_deferred" | null;

export interface AgentAction {
  kind: AgentActionKind;
  outcome: AgentOutcome;
}

/** `done` frame payload — terminal; persisted turn + grounded recommendations. */
export interface DoneEvent {
  conversation_id: string;
  message_id: string;
  action: AgentAction | null;
  recommendations: AgentRecommendation[];
  /** Disambiguation copy when the turn is a clarify (`agent-clarify-prompt`). */
  clarify?: string | null;
  /** Refusal copy when the turn is out-of-scope (`agent-refusal-notice`). */
  refusal?: string | null;
}

/** `error` frame payload — terminal; wraps the canonical error envelope body. */
export interface StreamError {
  error: ErrorBody;
}

/** Request body to start a conversation / send a follow-up message. */
export interface ConversationStartRequest {
  surface: AgentSurface;
  message: string;
  context?: { product_id?: string; order_id?: string } | null;
}

export interface MessageRequest {
  message: string;
  context?: { product_id?: string; order_id?: string } | null;
}
