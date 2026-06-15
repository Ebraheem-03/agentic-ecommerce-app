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
  email_verified: boolean;
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
 * cart — §cart `POST /cart/items` → `CartOut`. Only the slice the
 * product page needs for an optimistic add + confirmation.
 * ------------------------------------------------------------------ */

export interface CartItemAdd {
  variant_id: string;
  quantity: number;
}

export interface CartLine {
  id: string;
  variant_id: string;
  title: string;
  quantity: number;
  unit_price_cents: number;
}

export interface CartOut {
  id: string;
  lines: CartLine[];
  subtotal_cents: number;
  currency: string;
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
