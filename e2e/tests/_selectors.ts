// -----------------------------------------------------------------------------
// Canonical data-testid registry (typed mirror of docs/qa/test-ids.md).
//
// US-QA-D03: these constants are the single source of truth for selectors used
// by the J-* spec skeletons. They are documented BEFORE the frontend build, so
// Iris/Nova honor them as a contract. When a spec flips from `test.fixme` to a
// real test, it selects via `page.getByTestId(TID.<screen>.<element>)`.
//
// Keep this in lockstep with docs/qa/test-ids.md — adding a spec anchor means
// adding it both here and in that doc, in the same PR.
// -----------------------------------------------------------------------------

export const TID = {
  // Shared agent chat surface (cross-screen).
  agent: {
    chatPanel: "agent-chat-panel",
    thinkingIndicator: "agent-thinking-indicator",
    messageList: "agent-message-list",
    messageAssistant: "agent-message-assistant",
    messageUser: "agent-message-user",
    chatInput: "agent-chat-input",
    chatSend: "agent-chat-send",
    clarifyPrompt: "agent-clarify-prompt",
    recommendationCard: "agent-recommendation-card",
    recommendationReason: "agent-recommendation-reason",
    refusalNotice: "agent-refusal-notice",
    citation: "agent-citation",
  },
  home: {
    page: "home-page",
    heroCta: "home-hero-cta",
    searchEntry: "home-search-entry",
    featuredRail: "home-featured-rail",
    nav: "home-nav",
    cartLink: "home-cart-link",
  },
  search: {
    page: "search-page",
    input: "search-input",
    submit: "search-submit",
    results: "search-results",
    resultCard: "search-result-card",
    resultTitle: "search-result-title",
    resultPrice: "search-result-price",
    emptyState: "search-empty-state",
    filters: "search-filters",
  },
  product: {
    page: "product-page",
    title: "product-title",
    price: "product-price",
    image: "product-image",
    addToCart: "product-add-to-cart",
    outOfStock: "product-out-of-stock",
    qty: "product-qty",
    addConfirmation: "product-add-confirmation",
  },
  cart: {
    page: "cart-page",
    lineItem: "cart-line-item",
    lineTitle: "cart-line-title",
    lineQty: "cart-line-qty",
    lineRemove: "cart-line-remove",
    subtotal: "cart-subtotal",
    emptyState: "cart-empty-state",
    checkoutCta: "cart-checkout-cta",
  },
  checkout: {
    page: "checkout-page",
    addressForm: "checkout-address-form",
    addressLine1: "checkout-address-line1",
    addressError: "checkout-address-error",
    paymentForm: "checkout-payment-form",
    paymentError: "checkout-payment-error",
    orderSummary: "checkout-order-summary",
    placeOrder: "checkout-place-order",
    confirmation: "checkout-confirmation",
  },
  orderStatus: {
    page: "order-status-page",
    lookupInput: "order-status-lookup-input",
    lookupSubmit: "order-status-lookup-submit",
    timeline: "order-status-timeline",
    step: "order-status-step",
    summary: "order-status-summary",
    notFound: "order-status-not-found",
    returnCta: "order-status-return-cta",
    returnPanel: "order-status-return-panel",
    hitlPending: "order-status-hitl-pending",
  },
  seller: {
    page: "seller-dashboard-page",
    onboarding: "seller-dashboard-onboarding",
    profileIncomplete: "seller-dashboard-profile-incomplete",
    listForm: "seller-dashboard-list-form",
    listError: "seller-dashboard-list-error",
    listSubmit: "seller-dashboard-list-submit",
    nudge: "seller-dashboard-nudge",
    nudgeReason: "seller-dashboard-nudge-reason",
    nudgeAccept: "seller-dashboard-nudge-accept",
    publishAudit: "seller-dashboard-publish-audit",
    orders: "seller-dashboard-orders",
    fulfil: "seller-dashboard-fulfil",
  },
  support: {
    console: "support-console",
    escalateHitl: "support-escalate-hitl",
    auditLogEntry: "support-audit-log-entry",
  },
  admin: {
    console: "admin-console",
    policyTable: "admin-policy-table",
    guardrailEditor: "admin-guardrail-editor",
    guardrailSave: "admin-guardrail-save",
  },
} as const;
