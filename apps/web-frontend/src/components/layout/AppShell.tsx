import type { ReactNode } from "react";

import { AppHeader } from "./AppHeader";

type AppShellProps = {
  children: ReactNode;
  /** Shown in the top bar after the app title */
  headerMenuExtra?: ReactNode;
};

export function AppShell({ children, headerMenuExtra }: AppShellProps) {
  return (
    <div className="flex h-screen min-h-0 flex-col bg-background">
      <AppHeader menuExtra={headerMenuExtra} />
      <main className="min-h-0 flex-1 overflow-hidden p-2">{children}</main>
    </div>
  );
}
