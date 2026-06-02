"use client";

import type { ReactNode } from "react";
import { ToastProvider } from "@/context/ToastContext";
import { ApolloProvider } from "@/providers/ApolloProvider";
import { KeyboardShortcutsOverlay } from "@/components/terminal/KeyboardShortcutsOverlay";

interface ProvidersProps {
  children: ReactNode;
}

export function Providers({ children }: ProvidersProps) {
  return (
    <ApolloProvider>
      <ToastProvider>
        <KeyboardShortcutsOverlay />
        {children}
      </ToastProvider>
    </ApolloProvider>
  );
}

