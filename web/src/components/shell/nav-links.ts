/** Primary nav links, shared by the desktop and mobile nav. */
export interface NavLink {
  href: string;
  label: string;
}

export const PRIMARY_NAV: readonly NavLink[] = [
  { href: "/search", label: "Browse" },
  { href: "/search?view=collections", label: "Collections" },
  { href: "/search?view=makers", label: "Makers" },
  { href: "/seller", label: "Sell on Hearth" },
];
