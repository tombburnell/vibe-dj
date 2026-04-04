import { createContext, useContext } from "react";

export type SourceTopMatchContextValue = {
  isTopMatchLoading: (sourceTrackId: string) => boolean;
};

const defaultValue: SourceTopMatchContextValue = {
  isTopMatchLoading: () => false,
};

export const SourceTopMatchContext =
  createContext<SourceTopMatchContextValue>(defaultValue);

export function useSourceTopMatchLoading(): SourceTopMatchContextValue {
  return useContext(SourceTopMatchContext);
}
