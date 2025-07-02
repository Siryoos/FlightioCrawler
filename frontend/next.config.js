/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  output: 'standalone',
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: `${process.env.NEXT_PUBLIC_API_BASE || 'http://localhost:8000'}/api/:path*`,
      },
      {
        source: '/crawl',
        destination: `${process.env.NEXT_PUBLIC_API_BASE || 'http://localhost:8000'}/crawl`,
      },
      {
        source: '/health',
        destination: `${process.env.NEXT_PUBLIC_API_BASE || 'http://localhost:8000'}/health`,
      },
      {
        source: '/ws/:path*',
        destination: `${process.env.NEXT_PUBLIC_API_BASE || 'http://localhost:8000'}/ws/:path*`,
      },
    ]
  }
};

module.exports = nextConfig;
