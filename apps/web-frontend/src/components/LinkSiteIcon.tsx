/**
 * Link row icons via react-icons only (brands from Simple Icons + Font Awesome; generic from
 * Heroicons hi2). For Lucide elsewhere: npm install lucide-react in apps/web-frontend, then import.
 */
import { HiLink, HiMagnifyingGlass } from "react-icons/hi2";
import { FaAmazon } from "react-icons/fa6";
import { SiSoundcloud, SiTidal } from "react-icons/si";

/** Recognized purchase/stream hosts (matches API ``matched_domain`` / URL host). */
export type LinkSite = "tidal" | "amazon" | "soundcloud" | "search" | "other";

const iconBox = "inline-flex size-6 shrink-0 items-center justify-center text-current";

export function linkSiteFromUrl(url: string): LinkSite {
  try {
    const h = new URL(url).hostname.toLowerCase();
    if (h === "tidal.com" || h.endsWith(".tidal.com")) return "tidal";
    if (h === "amazon.com" || h.endsWith(".amazon.com")) return "amazon";
    if (h === "soundcloud.com" || h.endsWith(".soundcloud.com")) return "soundcloud";
    if (
      h.includes("brave.com") ||
      h.includes("duckduckgo.com") ||
      h.includes("google.com") ||
      h.endsWith("bing.com")
    ) {
      return "search";
    }
    return "other";
  } catch {
    return "other";
  }
}

export function LinkSiteIcon({ url, className = "" }: { url: string; className?: string }) {
  const site = linkSiteFromUrl(url);
  const wrap = `${iconBox} ${className}`.trim();

  if (site === "tidal") {
    return (
      <span className={wrap} title="TIDAL">
        <SiTidal className="size-5" aria-hidden />
      </span>
    );
  }
  if (site === "amazon") {
    return (
      <span className={wrap} title="Amazon">
        <FaAmazon className="size-5 text-[#FF9900]" aria-hidden />
      </span>
    );
  }
  if (site === "soundcloud") {
    return (
      <span className={wrap} title="SoundCloud">
        <SiSoundcloud className="size-5 text-[#FF5500]" aria-hidden />
      </span>
    );
  }
  if (site === "search") {
    return (
      <span className={wrap} title="Web search">
        <HiMagnifyingGlass className="size-5 text-violet-600 dark:text-violet-400" aria-hidden />
      </span>
    );
  }
  return (
    <span className={wrap} title="Link">
      <HiLink className="size-5 text-muted" aria-hidden />
    </span>
  );
}
