import type { NextConfig } from 'next';

const nextConfig: NextConfig = {
  serverExternalPackages: ['jsdom'],
  // Allow images from any domain for article extraction
  images: {
    remotePatterns: [
      {
        protocol: 'https',
        hostname: '**',
      },
      {
        protocol: 'http',
        hostname: '**',
      },
    ],
  },
};

export default nextConfig;
