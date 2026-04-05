import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from "react";

export const SKIP_WELCOME_KEY = "skip_welcome";

export type WelcomeModalTab = "welcome" | "help";

function readSkipWelcome(): boolean {
  try {
    return localStorage.getItem(SKIP_WELCOME_KEY) === "true";
  } catch {
    return false;
  }
}

type WelcomeModalContextValue = {
  isOpen: boolean;
  activeTab: WelcomeModalTab;
  setActiveTab: (tab: WelcomeModalTab) => void;
  dontShowAgain: boolean;
  setDontShowAgain: (value: boolean) => void;
  openWelcomeModal: (tab?: WelcomeModalTab) => void;
  closeWelcomeModal: () => void;
};

const WelcomeModalContext = createContext<WelcomeModalContextValue | null>(null);

export function WelcomeModalProvider({ children }: { children: ReactNode }) {
  const [isOpen, setIsOpen] = useState(() => !readSkipWelcome());
  const [activeTab, setActiveTab] = useState<WelcomeModalTab>("welcome");
  const [dontShowAgain, setDontShowAgain] = useState(false);

  const openWelcomeModal = useCallback((tab?: WelcomeModalTab) => {
    setActiveTab(tab ?? "help");
    setDontShowAgain(false);
    setIsOpen(true);
  }, []);

  const closeWelcomeModal = useCallback(() => {
    if (isOpen && activeTab === "welcome" && dontShowAgain) {
      try {
        localStorage.setItem(SKIP_WELCOME_KEY, "true");
      } catch {
        /* ignore */
      }
    }
    setIsOpen(false);
    setDontShowAgain(false);
  }, [isOpen, activeTab, dontShowAgain]);

  const value = useMemo(
    () => ({
      isOpen,
      activeTab,
      setActiveTab,
      dontShowAgain,
      setDontShowAgain,
      openWelcomeModal,
      closeWelcomeModal,
    }),
    [
      isOpen,
      activeTab,
      dontShowAgain,
      openWelcomeModal,
      closeWelcomeModal,
    ],
  );

  return (
    <WelcomeModalContext.Provider value={value}>{children}</WelcomeModalContext.Provider>
  );
}

export function useWelcomeModal() {
  const ctx = useContext(WelcomeModalContext);
  if (!ctx) {
    throw new Error("useWelcomeModal must be used within WelcomeModalProvider");
  }
  return ctx;
}
