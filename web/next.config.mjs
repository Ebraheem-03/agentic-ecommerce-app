/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Emit a standalone server bundle so the production Docker image stays small.
  output: "standalone",
};

export default nextConfig;
