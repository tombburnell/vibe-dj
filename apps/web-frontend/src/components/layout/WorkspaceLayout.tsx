type Props = {
  toolbar: React.ReactNode;
  primary: React.ReactNode;
  secondary: React.ReactNode;
};

/**
 * Primary table + docked secondary panel (desktop: side-by-side).
 */
export function WorkspaceLayout({ toolbar, primary, secondary }: Props) {
  return (
    <div className="flex h-full min-h-0 flex-col gap-2">
      <div className="shrink-0">{toolbar}</div>
      <div className="grid min-h-0 flex-1 grid-cols-1 gap-2 lg:grid-cols-[1fr_minmax(16rem,22rem)]">
        <div className="min-h-0 flex flex-col overflow-hidden">{primary}</div>
        <div className="min-h-0 flex flex-col overflow-hidden lg:max-h-none">{secondary}</div>
      </div>
    </div>
  );
}
