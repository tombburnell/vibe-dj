import { SettingsModal } from "@/components/settings/SettingsModal";
import { useSettingsModal } from "@/contexts/SettingsModalContext";

/** Renders the settings dialog; keep mounted under the modal context + router. */
export function SettingsModalHost() {
  const { isOpen, closeSettings } = useSettingsModal();
  return <SettingsModal open={isOpen} onClose={closeSettings} />;
}
