# ADR-0001: Technology Stack

## Context
The frontend of FlightioCrawler uses **Next.js 14** with **Server-Side Rendering** to optimize SEO for Persian flight searches. **Zustand** and **React Query** manage client state and caching, providing simple hooks-based APIs. **Tailwind CSS** with **Radix UI** ensures consistent styling and accessibility in RTL layouts. Real-time updates are planned using **Socket.io**.

## Decision
We continue with this stack because:
- Next.js 14 offers fast SSR, automatic code splitting and good SEO.
- Zustand provides lightweight global state without boilerplate.
- React Query handles data fetching and caching across pages.
- Tailwind + Radix UI allow rapid development with RTL support.
- Socket.io gives reliable WebSocket communication for crawler status and price updates.

## Consequences
- Developers should follow a component-driven approach using these tools.
- Additional monitoring of bundle size is required to meet performance goals.
