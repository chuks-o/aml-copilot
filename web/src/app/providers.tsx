"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState, type ReactNode } from "react";
import { Client, Provider as UrqlProvider, cacheExchange, fetchExchange } from "urql";

import { GRAPHQL_URL } from "@/lib/config";

/**
 * urql handles all GraphQL (/api/graphql); TanStack Query handles any
 * non-GraphQL server state. See docs/decisions/0008.
 */
export function Providers({ children }: { children: ReactNode }) {
  const [urqlClient] = useState(
    () => new Client({ url: GRAPHQL_URL, exchanges: [cacheExchange, fetchExchange] }),
  );
  const [queryClient] = useState(() => new QueryClient());

  return (
    <UrqlProvider value={urqlClient}>
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    </UrqlProvider>
  );
}
