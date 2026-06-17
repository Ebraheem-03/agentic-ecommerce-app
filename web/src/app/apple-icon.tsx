import { ImageResponse } from "next/og";

/**
 * Apple touch icon — the Hearth "Keystone" mark at 180×180 on the warm brand
 * surface (Next file-based `apple-icon` convention). Same duotone geometry as
 * `app/icon`, scaled up with safe padding for the rounded-mask treatment iOS
 * applies to home-screen icons.
 */
export const size = { width: 180, height: 180 };
export const contentType = "image/png";

export default function AppleIcon(): ImageResponse {
  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          background: "#faf8f6",
        }}
      >
        <svg
          width="132"
          height="132"
          viewBox="0 0 64 64"
          xmlns="http://www.w3.org/2000/svg"
        >
          <path
            d="M32 8 L54 21 C56 22.2, 56 25, 54 26.2 L34 38 C32.8 38.7, 31.2 38.7, 30 38 L10 26.2 C8 25, 8 22.2, 10 21 Z"
            fill="#b5512f"
          />
          <path
            d="M32 28 L50 38.5 C52 39.7, 52 42.5, 50 43.7 L34 53 C32.8 53.7, 31.2 53.7, 30 53 L14 43.7 C12 42.5, 12 39.7, 14 38.5 Z"
            fill="#e08a3c"
          />
        </svg>
      </div>
    ),
    size,
  );
}
