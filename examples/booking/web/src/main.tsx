import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { TooltipProvider } from "@radix-ui/react-tooltip";

import "@fontsource-variable/geist/index.css";

import Atlas from "./pages/Atlas";
import Console from "./pages/Console";
import Onboard from "./pages/Onboard";

// Order matters: tokens defines CSS custom properties consumed by both
// Tailwind's @theme block and the legacy styles.css aliases.
import "./styles/tokens.css";
import "./styles/tailwind.css";
import "./styles.css";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
});

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <TooltipProvider delayDuration={250}>
        <BrowserRouter>
          <Routes>
            <Route index element={<Navigate to="/atlas" replace />} />
            <Route path="atlas" element={<Atlas />} />
            <Route path="console" element={<Console />} />
            <Route path="onboard" element={<Onboard />} />
            <Route path="*" element={<Navigate to="/atlas" replace />} />
          </Routes>
        </BrowserRouter>
      </TooltipProvider>
    </QueryClientProvider>
  </React.StrictMode>,
);
