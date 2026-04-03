import { AppHeader } from "./AppHeader";

export function AppShell({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex h-screen min-h-0 flex-col bg-background">
      <AppHeader />
      <main className="min-h-0 flex-1 overflow-hidden p-2">{children}</main>
    </div>
  );
}
