/**
 * Link row icons via react-icons only (brands from Simple Icons + Font Awesome; generic from
 * Heroicons hi2). For Lucide elsewhere: npm install lucide-react in apps/web-frontend, then import.
 */
import { HiLink, HiMagnifyingGlass } from "react-icons/hi2";
import { FaAmazon } from "react-icons/fa6";
import { SiBandcamp, SiSoundcloud, SiTidal, SiYoutube } from "react-icons/si";

/** Recognized purchase/stream hosts (matches API ``matched_domain`` / URL host). */
export type LinkSite =
  | "tidal"
  | "amazon"
  | "soundcloud"
  | "bandcamp"
  | "beatport"
  | "youtube"
  | "search"
  | "other";

/** Simple Icons v14 Beatport mark (no ``SiBeatport`` in this react-icons build). */
function BeatportGlyph({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      role="img"
      viewBox="0 0 24 24"
      xmlns="http://www.w3.org/2000/svg"
      aria-hidden
    >
      <path
        fill="currentColor"
        d="M21.429 17.055a7.114 7.114 0 0 1-.794 3.246 6.917 6.917 0 0 1-2.181 2.492 6.698 6.698 0 0 1-3.063 1.163 6.653 6.653 0 0 1-3.239-.434 6.796 6.796 0 0 1-2.668-1.932 7.03 7.03 0 0 1-1.481-2.983 7.124 7.124 0 0 1 .049-3.345 7.015 7.015 0 0 1 1.566-2.937l-4.626 4.73-2.421-2.479 5.201-5.265a3.791 3.791 0 0 0 1.066-2.675V0h3.41v6.613a7.172 7.172 0 0 1-.519 2.794 7.02 7.02 0 0 1-1.559 2.353l-.153.156a6.768 6.768 0 0 1 3.49-1.725 6.687 6.687 0 0 1 3.845.5 6.873 6.873 0 0 1 2.959 2.564 7.118 7.118 0 0 1 1.118 3.8Zm-3.089 0a3.89 3.89 0 0 0-.611-2.133 3.752 3.752 0 0 0-1.666-1.424 3.65 3.65 0 0 0-2.158-.233 3.704 3.704 0 0 0-1.92 1.037 3.852 3.852 0 0 0-1.031 1.955 3.908 3.908 0 0 0 .205 2.213c.282.7.76 1.299 1.374 1.721a3.672 3.672 0 0 0 2.076.647 3.637 3.637 0 0 0 2.635-1.096c.347-.351.622-.77.81-1.231.188-.461.285-.956.286-1.456Z"
      />
    </svg>
  );
}

const iconBox = "inline-flex size-6 shrink-0 items-center justify-center text-current";

export function linkSiteFromUrl(url: string): LinkSite {
  try {
    const h = new URL(url).hostname.toLowerCase();
    if (h === "tidal.com" || h.endsWith(".tidal.com")) return "tidal";
    if (h === "amazon.com" || h.endsWith(".amazon.com")) return "amazon";
    if (h === "soundcloud.com" || h.endsWith(".soundcloud.com")) return "soundcloud";
    if (h === "bandcamp.com" || h.endsWith(".bandcamp.com")) return "bandcamp";
    if (h === "beatport.com" || h.endsWith(".beatport.com")) return "beatport";
    if (h === "youtu.be" || h.endsWith(".youtu.be")) return "youtube";
    if (h === "youtube.com" || h.endsWith(".youtube.com")) return "youtube";
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
  if (site === "bandcamp") {
    return (
      <span className={wrap} title="Bandcamp">
        <SiBandcamp className="size-5 text-[#629AA9]" aria-hidden />
      </span>
    );
  }
  if (site === "beatport") {
    return (
      <span className={wrap} title="Beatport">
        <BeatportGlyph className="size-5 text-[#01ff95]" aria-hidden />
      </span>
    );
  }
  if (site === "youtube") {
    return (
      <span className={wrap} title="YouTube">
        <SiYoutube className="size-5 text-[#FF0000]" aria-hidden />
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
