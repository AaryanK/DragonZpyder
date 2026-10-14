// Time-only image state: the existing OpenRouter /images request returns
// one completed image, not intermediate frames or provider progress events.
export function formatImageWait(elapsedMs) {
  const elapsedSeconds = Math.max(0, Math.floor(
    Number.isFinite(elapsedMs) ? elapsedMs / 1000 : 0
  ));
  const minutes = Math.floor(elapsedSeconds / 60);
  const seconds = String(elapsedSeconds % 60).padStart(2, "0");
  return "Waiting for provider · " + minutes + ":" + seconds + " elapsed";
}
