import { FaCirclePlay } from "react-icons/fa6";

type Props = {
  spotifyId: string | null | undefined;
};

/** Opens the track in the Spotify desktop app via ``spotify:track:`` URI (requires Spotify installed). */
export function SpotifyPlayCell({ spotifyId }: Props) {
  const id = spotifyId?.trim();
  if (!id) {
    return (
      <span
        className="text-[length:var(--text-src-triple)] text-muted"
        title="No Spotify track id"
      >
        —
      </span>
    );
  }
  return (
    <a
      href={`spotify:track:${id}`}
      title="Play in Spotify"
      className="inline-flex items-center justify-center rounded p-0.5 text-accent hover:bg-surface-2 hover:opacity-90 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-accent"
      aria-label="Play in Spotify"
    >
      <FaCirclePlay
        className="h-[1.1em] w-[1.1em] min-h-[15px] min-w-[15px]"
        aria-hidden
      />
    </a>
  );
}
